"""Geometry facts stay revision-bound and unknown when prerequisites fail."""
from pathlib import Path
import tempfile
import unittest

import ifcopenshell
import ifcopenshell.guid

from ifc_engine.geometry import GeometryProvider, _compare_boundaries, _locate
from ifc_engine.ingest import file_sha256, load_ifc


def geometry_source(path, *, millimetres=False, rotate=False):
    model=ifcopenshell.file(schema="IFC4")
    scale=1000. if millimetres else 1.
    def root(kind,**kw):
        return model.create_entity(kind,GlobalId=ifcopenshell.guid.new(),**kw)
    def point(coords):
        return model.createIfcCartesianPoint(tuple(float(x)*scale for x in coords))
    def axis(coords=(0.,0.,0.)):
        return model.createIfcAxis2Placement3D(point(coords),None,None)
    def placement(coords=(0.,0.,0.)):
        return model.createIfcLocalPlacement(None,axis(coords))
    unit=model.createIfcSIUnit(None,"LENGTHUNIT","MILLI" if millimetres else None,"METRE")
    project=root("IfcProject",Name="Geometry fixture",UnitsInContext=model.createIfcUnitAssignment([unit]))
    context=model.createIfcGeometricRepresentationContext(None,"Model",3,1e-5,axis(),None)
    project.RepresentationContexts=[context]
    def box(element,dimensions,origin=(0.,0.,0.)):
        x,y,z=dimensions
        profile=model.createIfcArbitraryClosedProfileDef("AREA",None,model.createIfcPolyline([
            point(p) for p in [(0.,0.),(x,0.),(x,y),(0.,y),(0.,0.)]]))
        solid=model.createIfcExtrudedAreaSolid(profile,axis(),model.createIfcDirection((0.,0.,1.)),z*scale)
        representation=model.createIfcShapeRepresentation(context,"Body","SweptSolid",[solid])
        element.Representation=model.createIfcProductDefinitionShape(None,None,[representation])
        element.ObjectPlacement=placement(origin)
    a=root("IfcSpace",Name="1B07",ObjectPlacement=placement())
    b=root("IfcSpace",Name="121.A",ObjectPlacement=placement())
    wall=root("IfcWall",Name="Shared long wall")
    box(wall,(5.,.2,3.))
    def boundary(space,start,end,*,offset=(0.,0.,0.)):
        curve=model.createIfcPolyline([point(start),point(end)])
        profile=model.createIfcArbitraryOpenProfileDef("CURVE",None,curve)
        surface=model.createIfcSurfaceOfLinearExtrusion(profile,axis(offset),model.createIfcDirection((0.,0.,1.)),3.*scale)
        return root("IfcRelSpaceBoundary",RelatingSpace=space,RelatedBuildingElement=wall,
            ConnectionGeometry=model.createIfcConnectionSurfaceGeometry(surface,None),
            PhysicalOrVirtualBoundary="PHYSICAL",InternalOrExternalBoundary="INTERNAL")
    ba=boundary(a,(0.,0.),(5.,0.))
    bb=boundary(b,(4.,0.),(1.,0.))
    if rotate:
        for space in (a,b):
            space.ObjectPlacement.RelativePlacement.RefDirection=model.createIfcDirection((0.,1.,0.))
            space.ObjectPlacement.RelativePlacement.Location=point((20.,30.,4.))
    room=root("IfcSpace",Name="Convex room")
    box(room,(5.,5.,3.))
    equipment=root("IfcBuildingElementProxy",Name="Panel-01")
    box(equipment,(1.,1.,1.),(1.,1.,1.))
    if rotate:
        for element in (room,equipment):
            element.ObjectPlacement.RelativePlacement.RefDirection=model.createIfcDirection((0.,1.,0.))
        equipment.ObjectPlacement.RelativePlacement.Location=point((-1.,1.,1.))
    model.write(str(path))
    return model, {"a":a,"b":b,"wall":wall,"ba":ba,"bb":bb,"room":room,"equipment":equipment,"boundary":boundary,"point":point}


class IfcGeometryTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.path=Path(self.directory.name)/"geometry.ifc"
        self.model,self.objects=geometry_source(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def compare(self):
        return _compare_boundaries(self.model,self.objects["ba"].id(),self.objects["bb"].id(),.01)

    def test_overlapping_native_patches_match_with_computation_inputs(self):
        result=self.compare()
        self.assertEqual(result["status"],"match")
        self.assertAlmostEqual(result["overlap_area_m2"],9.)
        self.assertEqual(result["host_step_id"],self.objects["wall"].id())
        self.assertEqual(len(result["patch_a_m"]),4)

    def test_shared_long_wall_does_not_prove_adjacency_of_disjoint_patches(self):
        self.objects["bb"]=self.objects["boundary"](self.objects["b"],(9.,0.),(6.,0.))
        self.assertEqual(self.compare()["status"],"no_match")

    def test_long_thin_overlap_with_large_area_remains_within_tolerance(self):
        # A 3 m tall, 5 mm overlap exceeds tol² in area but cannot establish a
        # stable positive overlap under the declared 10 mm length tolerance.
        self.objects["bb"]=self.objects["boundary"](self.objects["b"],(8.,0.),(4.995,0.))
        self.assertEqual(self.compare()["status"],"unknown")

    def test_vertical_separation_and_same_facing_patches_are_not_matches(self):
        self.objects["bb"]=self.objects["boundary"](self.objects["b"],(4.,0.),(1.,0.),offset=(0.,0.,5.))
        self.assertEqual(self.compare()["status"],"no_match")
        self.objects["bb"]=self.objects["boundary"](self.objects["b"],(1.,0.),(4.,0.))
        self.assertEqual(self.compare()["status"],"unknown")

    def test_opposed_patches_allow_verified_wall_thickness_but_not_unbounded_gap(self):
        self.objects["bb"]=self.objects["boundary"](self.objects["b"],(4.,.2),(1.,.2))
        self.assertEqual(self.compare()["status"],"match")
        self.objects["bb"]=self.objects["boundary"](self.objects["b"],(4.,5.),(1.,5.))
        self.assertEqual(self.compare()["status"],"unknown")

    def test_rotated_millimetre_patches_are_compared_in_world_metres(self):
        self.model,self.objects=geometry_source(self.path,millimetres=True,rotate=True)
        self.assertEqual(self.compare()["status"],"match")
        self.assertAlmostEqual(self.compare()["overlap_area_m2"],9.)
        self.assertEqual(self.compare()["patch_a_m"][0],[20.,30.,4.])

    def test_containment_uses_whole_object_and_marks_face_tolerance_unknown(self):
        obj,room=self.objects["equipment"],self.objects["room"]
        result=_locate(self.model,obj.id(),[room.id()],.01)
        self.assertEqual(result["matched_step_ids"],[room.id()])
        obj.ObjectPlacement.RelativePlacement.Location=self.objects["point"]((4.5,1.,1.))
        self.assertEqual(_locate(self.model,obj.id(),[room.id()],.01)["matched_step_ids"],[])
        obj.ObjectPlacement.RelativePlacement.Location=self.objects["point"]((0.,1.,1.))
        self.assertEqual(_locate(self.model,obj.id(),[room.id()],.01)["unresolved_step_ids"],[room.id()])

    def test_rotated_millimetre_whole_object_containment(self):
        self.model,self.objects=geometry_source(self.path,millimetres=True,rotate=True)
        result=_locate(self.model,self.objects["equipment"].id(),[self.objects["room"].id()],.01)
        self.assertEqual(result["matched_step_ids"],[self.objects["room"].id()])

    def test_missing_geometry_is_unknown_without_origin_guess(self):
        self.objects["equipment"].Representation=None
        result=_locate(self.model,self.objects["equipment"].id(),[self.objects["room"].id()],.01)
        self.assertEqual(result["status"],"unknown")

    def test_nonconvex_room_shape_remains_unresolved(self):
        room=self.objects["room"]
        profile=room.Representation.Representations[0].Items[0].SweptArea
        profile.OuterCurve.Points=[self.objects["point"](p) for p in [
            (0.,0.),(5.,0.),(5.,1.),(1.,1.),(1.,5.),(0.,5.),(0.,0.)]]
        result=_locate(self.model,self.objects["equipment"].id(),[room.id()],.01)
        self.assertEqual(result["unresolved_step_ids"],[room.id()])

    def test_open_object_surface_inside_room_does_not_prove_whole_object_containment(self):
        equipment=self.objects["equipment"]
        coordinates=[(0.,0.,0.),(1.,0.,0.),(1.,1.,0.),(0.,1.,0.),
                     (0.,0.,1.),(1.,0.,1.),(1.,1.,1.),(0.,1.,1.)]
        points=[self.objects["point"](p) for p in coordinates]
        # The upper face is absent: this is an explicitly open source mesh.
        faces=[]
        for indices in [(0,3,2,1),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
            loop=self.model.createIfcPolyLoop([points[i] for i in indices])
            faces.append(self.model.createIfcFace([self.model.createIfcFaceOuterBound(loop,True)]))
        surface=self.model.createIfcFaceBasedSurfaceModel([self.model.createIfcConnectedFaceSet(faces)])
        representation=equipment.Representation.Representations[0]
        representation.RepresentationType="SurfaceModel"
        representation.Items=[surface]
        room=self.objects["room"]
        result=_locate(self.model,equipment.id(),[room.id()],.01)
        self.assertEqual(result["status"],"unknown")
        self.assertEqual(result["unresolved_step_ids"],[room.id()])

    def test_closed_nonconvex_object_can_be_contained_in_convex_room(self):
        equipment=self.objects["equipment"]
        profile=equipment.Representation.Representations[0].Items[0].SweptArea
        profile.OuterCurve.Points=[self.objects["point"](p) for p in [
            (0.,0.),(2.,0.),(2.,.5),(.5,.5),(.5,2.),(0.,2.),(0.,0.)]]
        room=self.objects["room"]
        result=_locate(self.model,equipment.id(),[room.id()],.01)
        self.assertEqual(result["matched_step_ids"],[room.id()])

    def test_missing_or_ambiguous_length_units_do_not_default_to_metres(self):
        project=self.model.by_type("IfcProject")[0]
        project.UnitsInContext=None
        result=_locate(self.model,self.objects["equipment"].id(),[self.objects["room"].id()],.01)
        self.assertEqual(result["status"],"unknown")
        self.model.write(str(self.path))
        provider=GeometryProvider(self.path,file_sha256(self.path))
        result=provider.compare_boundaries(self.objects["ba"].id(),self.objects["bb"].id())
        self.assertEqual(result["status"],"unknown")

    def test_isolated_provider_handles_missing_geometry_and_rejects_stale_revision(self):
        provider=GeometryProvider(self.path,file_sha256(self.path))
        result=provider.compare_boundaries(self.objects["ba"].id(),self.objects["bb"].id())
        self.assertEqual(result["status"],"match")
        self.assertEqual(result["frame"],"ifc_world")
        self.path.write_text(self.path.read_text()+"\n")
        self.assertEqual(provider.compare_boundaries(self.objects["ba"].id(),self.objects["bb"].id())["status"],"unknown")
        self.assertEqual(provider.locate_in_spaces(1,[],timeout_seconds=0)["status"],"unknown")

    def test_native_failure_is_a_structured_unknown_and_does_not_poison_cache(self):
        provider=GeometryProvider(self.path,file_sha256(self.path))
        result=provider.compare_boundaries(99999999,self.objects["bb"].id())
        self.assertEqual(result["status"],"unknown")
        self.assertEqual(len(provider._cache),0)
        valid=provider.compare_boundaries(self.objects["ba"].id(),self.objects["bb"].id())
        self.assertEqual(valid["status"],"match")

    def test_boundary_records_preserve_unbound_and_undefined_metadata(self):
        boundary=self.objects["bb"]
        boundary.PhysicalOrVirtualBoundary="NOTDEFINED"
        boundary.RelatedBuildingElement=None
        self.model.write(str(self.path))
        bundle=load_ifc(self.path).bundle
        record=next(item for item in bundle.space_boundaries if item.native_step_id==boundary.id())
        self.assertEqual(record.physical_or_virtual,"NOTDEFINED")
        self.assertIsNone(record.element_id)
        self.assertEqual(record.connection_geometry_step_id,boundary.ConnectionGeometry.id())


if __name__=="__main__":
    unittest.main()
