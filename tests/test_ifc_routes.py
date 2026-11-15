"""Native walking paths preserve room/opening geometry and scope qualifications."""
from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ifcopenshell
import ifcopenshell.guid
from shapely.geometry import Polygon, LineString

from contracts import models as m
from contracts.validation import validate_plan, validate_result
from ifc_engine.catalog import POLICIES
from ifc_engine.engine import IfcQueryEngine
from ifc_engine.geometry import GeometryProvider
from ifc_engine.ingest import file_sha256
from ifc_engine.route_geometry import route_batch, _inside_path, _dijkstra


def route_source(path, *, millimetres=False, virtual=False):
    model = ifcopenshell.file(schema="IFC4")
    scale = 1000. if millimetres else 1.
    def root(kind, **kwargs): return model.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **kwargs)
    def point(coords): return model.createIfcCartesianPoint(tuple(float(v)*scale for v in coords))
    def axis(coords=(0.,0.,0.)): return model.createIfcAxis2Placement3D(point(coords),None,None)
    def placement(coords=(0.,0.,0.)): return model.createIfcLocalPlacement(None,axis(coords))
    unit = model.createIfcSIUnit(None,"LENGTHUNIT","MILLI" if millimetres else None,"METRE")
    project = root("IfcProject",Name="Routes",UnitsInContext=model.createIfcUnitAssignment([unit]))
    context = model.createIfcGeometricRepresentationContext(None,"Model",3,1e-5,axis(),None)
    project.RepresentationContexts=[context]
    def box(obj, x,y,width,depth,z=0.,height=3.):
        profile=model.createIfcArbitraryClosedProfileDef("AREA",None,model.createIfcPolyline([point(p) for p in [(0.,0.),(width,0.),(width,depth),(0.,depth),(0.,0.)]]))
        solid=model.createIfcExtrudedAreaSolid(profile,axis(),model.createIfcDirection((0.,0.,1.)),height*scale)
        obj.ObjectPlacement=placement((x,y,z))
        obj.Representation=model.createIfcProductDefinitionShape(None,None,[model.createIfcShapeRepresentation(context,"Body","SweptSolid",[solid])])
    def space(name,x,y,width,depth,z=0.):
        obj=root("IfcSpace",Name=name);box(obj,x,y,width,depth,z=z);return obj
    a=space("Origin",0,0,4,4)
    b=space("Corridor",4 if virtual else 4.2,0,4,4)
    c=space("Exit room",8 if virtual else 8.4,0,4,4)
    boundaries=[];doors=[];openings=[]
    def boundary(room,element,external=False,surface=None,kind="PHYSICAL"):
        obj=root("IfcRelSpaceBoundary",RelatingSpace=room,RelatedBuildingElement=element,PhysicalOrVirtualBoundary=kind,
            InternalOrExternalBoundary="EXTERNAL" if external else "INTERNAL",ConnectionGeometry=model.createIfcConnectionSurfaceGeometry(surface,None) if surface else None)
        boundaries.append(obj);return obj
    def door(name,x,rooms,external=False):
        door=root("IfcDoor",Name=name,OverallWidth=1.*scale)
        opening=root("IfcOpeningElement",Name=name+" opening")
        box(opening,x,1.5,.2,1.,height=2.1)
        root("IfcRelFillsElement",RelatingOpeningElement=opening,RelatedBuildingElement=door)
        for room in rooms: boundary(room,door,external)
        doors.append(door);openings.append(opening);return door
    if virtual:
        for room,start,end in [(a,(4.,0.),(4.,4.)),(b,(0.,4.),(0.,0.))]:
            curve=model.createIfcPolyline([point(start),point(end)])
            surface=model.createIfcSurfaceOfLinearExtrusion(model.createIfcArbitraryOpenProfileDef("CURVE",None,curve),axis(),model.createIfcDirection((0.,0.,1.)),3.*scale)
            boundary(room,None,surface=surface,kind="VIRTUAL")
        # Opening spans the two touching source room sides.
        door("Middle",8.,[b,c])
        # Avoid an artificial overlapping region in this fixture: move c by the
        # modeled opening's thickness, and extend b only to x8.
        box(c,8.2,0,4,4)
        external=door("Outdoor",12.2,[c],True)
    else:
        door("First",4.,[a,b]);door("Middle",8.2,[b,c]);external=door("Outdoor",12.4,[c],True)
    model.write(str(path))
    return model,{"a":a,"b":b,"c":c,"doors":doors,"openings":openings,"boundaries":boundaries,"external":external,"space":space,"box":box,"root":root,"point":point,"axis":axis,"context":context}


def options(model, objects, subjects=None):
    return {**{key:{str(o.id()):o.id() for o in model.by_type(cls)} for key,cls in
        [("rooms","IfcSpace"),("doors","IfcDoor"),("openings","IfcOpeningElement"),("stairs","IfcStairFlight")]},
        "subjects":subjects or [str(objects["a"].id())], "boundaries":[o.id() for o in model.by_type("IfcRelSpaceBoundary")],
        "targets":None,"include_stairs":True,"mode":"shortest","start_basis":"modeled_interior_point"}


class IfcRouteTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.path=Path(self.directory.name)/"route.ifc"
        self.model,self.objects=route_source(self.path)
    def tearDown(self): self.directory.cleanup()
    def result(self, **kwargs):
        result=route_batch(self.model,{**options(self.model,self.objects),**kwargs},.001)
        self.assertEqual(result["status"],"match",result)
        return result["records"][0]
    def test_dijkstra_finds_nearest_target_with_weighted_edges(self):
        graph={0:[(1,10),(2,2)],1:[(0,10),(2,1)],2:[(0,2),(1,1)]}
        distances,following=_dijkstra(graph,[1]);self.assertEqual(distances[0],3);self.assertEqual(following[0],2)
    def test_visibility_path_respects_concavity_and_holes(self):
        polygon=Polygon([(0,0),(6,0),(6,6),(0,6)],holes=[[(2,1),(4,1),(4,5),(2,5)]])
        path=_inside_path(polygon,(1,3),(5,3))
        self.assertGreater(len(path),2)
        self.assertGreater(sum(math.dist(a,b) for a,b in zip(path,path[1:])),4)
        for a,b in zip(path,path[1:]):self.assertTrue(polygon.covers(LineString([a,b])))
        self.assertIsNone(_inside_path(polygon,(3,3),(5,3)))
    def test_modeled_route_uses_opening_bridges_and_reports_distinct_widths(self):
        r=self.result();self.assertEqual(r["status"],"partial")
        self.assertEqual(r["room_ids"],[str(self.objects[k].id()) for k in ("a","b","c")])
        self.assertEqual(len(r["door_ids"]),3)
        self.assertAlmostEqual(sum(math.dist(a,b) for a,b in zip(r["path_points_m"],r["path_points_m"][1:])),r["metadata"]["distance_m"])
        self.assertEqual(r["metadata"]["nominal_door_width_m"],1.)
        self.assertEqual(r["metadata"]["geometric_opening_width_m"],1.)
        self.assertIsNone(r["metadata"]["sampled_clearance_m"])
        self.assertEqual(r["metadata"]["certification_status"],"unavailable")
        self.assertTrue(all(check["kind"] in {"room","door"} for check in r["metadata"]["path_checks"]))
    def test_shared_wall_without_modeled_opening_does_not_create_route(self):
        first=self.objects["doors"][0]
        self.model.remove(next(r for r in self.model.by_type("IfcRelFillsElement") if r.RelatedBuildingElement==first))
        r=route_batch(self.model,options(self.model,self.objects),.001)["records"][0]
        self.assertEqual(r["status"],"unavailable");self.assertFalse(r["path_points_m"])
    def test_native_virtual_open_passage_connects_rooms(self):
        self.model,self.objects=route_source(self.path,virtual=True)
        r=self.result();self.assertTrue(any(p["kind"]=="virtual_open_passage" for p in r["metadata"]["path_checks"]))
    def test_missing_room_body_is_not_replaced_by_other_geometry(self):
        self.objects["b"].Representation=None
        r=route_batch(self.model,options(self.model,self.objects),.001)["records"][0]
        self.assertEqual(r["status"],"unavailable")
        self.assertTrue(any(v["reason"]=="room_body_unavailable" for v in r["metadata"]["unresolved_inventory"]))
    def test_explicit_start_outside_room_is_unavailable(self):
        r=route_batch(self.model,{**options(self.model,self.objects),"start_basis":"explicit_point","start_point_m":(99.,99.,0.)},.001)["records"][0]
        self.assertEqual(r["status"],"unavailable")
    def test_hidden_opening_cannot_be_used_from_native_model(self):
        op=options(self.model,self.objects);op["openings"].pop(str(self.objects["openings"][0].id()))
        r=route_batch(self.model,op,.001)["records"][0]
        self.assertEqual(r["status"],"unavailable")
        self.assertTrue(any(v["reason"]=="opening_missing_or_outside_scope" for v in r["metadata"]["unresolved_inventory"]))
    def test_millimetre_units_and_worker_source_hash(self):
        self.model,self.objects=route_source(self.path,millimetres=True)
        r=self.result();self.assertEqual(r["metadata"]["nominal_door_width_m"],1.)
        provider=GeometryProvider(self.path,file_sha256(self.path));batch=provider.route_many(options(self.model,self.objects))
        self.assertEqual(batch["status"],"match",batch)
        self.path.write_bytes(self.path.read_bytes()+b"\n")
        self.assertEqual(provider.route_many(options(self.model,self.objects))["status"],"unknown")
    def test_literal_fire_exit_label_is_not_boolean_certification(self):
        p=self.objects["root"]("IfcPropertySet",Name="Flags",HasProperties=[self.model.createIfcPropertySingleValue("IsFireExit",None,self.model.create_entity("IfcLabel","IsFireExit"),None)])
        self.objects["root"]("IfcRelDefinesByProperties",RelatedObjects=[self.objects["external"]],RelatingPropertyDefinition=p)
        self.assertEqual(self.result()["metadata"]["certification_status"],"unavailable")
    def test_certified_target_basis_uses_positive_targets_when_available(self):
        p=self.objects["root"]("IfcPropertySet",Name="Flags",HasProperties=[self.model.createIfcPropertySingleValue("IsFireExit",None,self.model.create_entity("IfcBoolean",True),None)])
        self.objects["root"]("IfcRelDefinesByProperties",RelatedObjects=[self.objects["external"]],RelatingPropertyDefinition=p)
        near=self.objects["root"]("IfcDoor",Name="Near uncertified outdoor",OverallWidth=1.)
        opening=self.objects["root"]("IfcOpeningElement",Name="Near opening")
        self.objects["box"](opening,-.2,1.5,.2,1.,height=2.1)
        self.objects["root"]("IfcRelFillsElement",RelatingOpeningElement=opening,RelatedBuildingElement=near)
        self.objects["root"]("IfcRelSpaceBoundary",RelatingSpace=self.objects["a"],RelatedBuildingElement=near,
            PhysicalOrVirtualBoundary="PHYSICAL",InternalOrExternalBoundary="EXTERNAL")
        self.assertEqual(self.result()["target_id"],str(near.id()))
        r=self.result(target_basis="certified_fire_exit")
        self.assertEqual(r["target_id"],str(self.objects["external"].id()))
        self.assertEqual(r["metadata"]["target_basis_used"],"certified_fire_exit")
        self.assertFalse(r["metadata"]["certification_requested_unavailable"])
    def test_missing_certification_returns_explicit_potential_outdoor_fallback(self):
        r=self.result(target_basis="certified_fire_exit")
        self.assertEqual(r["metadata"]["target_basis_used"],"recorded_external_boundary")
        self.assertTrue(r["metadata"]["certification_requested_unavailable"])
    def test_farthest_search_includes_interior_samples_between_exits(self):
        # Vertices alone put a two-exit corridor's worst point near an exit;
        # interior sampling must find its middle instead.
        from ifc_engine.route_geometry import _samples
        polygon=Polygon([(0,0),(10,0),(10,2),(0,2)])
        samples,resolution=_samples(polygon,200)
        distance=lambda p:min(math.dist(p,(0,1)),math.dist(p,(10,1)))
        self.assertGreater(max(map(distance,samples)),4.9)
        self.assertLess(max(distance(p) for p in list(polygon.exterior.coords)),1.01)
        self.assertLessEqual(len(samples),200);self.assertGreater(resolution,0)
    def test_native_stair_walking_line_connects_supported_room_floors(self):
        upper=self.objects["space"]("Upper room",0,0,4,4,z=1.)
        stair=self.objects["root"]("IfcStairFlight",Name="Native flight",NumberOfRisers=5,NumberOfTreads=4,RiserHeight=.2,TreadLength=.5)
        profile=self.model.createIfcArbitraryClosedProfileDef("AREA",None,self.model.createIfcPolyline([self.objects["point"](p) for p in [(0,0),(2,1),(2,1.1),(0,.1),(0,0)]]))
        axis=self.model.createIfcAxis2Placement3D(self.objects["point"]((0,0,0)),self.model.createIfcDirection((0.,-1.,0.)),self.model.createIfcDirection((1.,0.,0.)))
        solid=self.model.createIfcExtrudedAreaSolid(profile,axis,self.model.createIfcDirection((0.,0.,1.)),1.)
        stair.ObjectPlacement=self.model.createIfcLocalPlacement(None,self.objects["axis"]((1,1.5,0)))
        walking=self.model.createIfcPolyline([self.objects["point"]((0.,-.5)),self.objects["point"]((2.,-.5))])
        stair.Representation=self.model.createIfcProductDefinitionShape(None,None,[self.model.createIfcShapeRepresentation(self.objects["context"],"Body","SweptSolid",[solid]),self.model.createIfcShapeRepresentation(self.objects["context"],"WalkingLine","Curve2D",[walking])])
        # IFC4 uses NumberOfRisers, while the supplied IFC2X3 source uses singular.
        r=self.result(subjects=[str(upper.id())])
        self.assertEqual(r["stair_ids"],[str(stair.id())]);self.assertGreater(r["metadata"]["distance_m"],10)
    def test_scope_change_after_warm_cache_never_reuses_hidden_opening(self):
        provider=GeometryProvider(self.path,file_sha256(self.path));full=options(self.model,self.objects)
        self.assertEqual(provider.route_many(full)["status"],"match")
        scoped={**full,"openings":dict(full["openings"])};scoped["openings"].pop(str(self.objects["openings"][0].id()))
        observed=provider.route_many(scoped)
        self.assertEqual(observed["status"],"unknown");self.assertFalse(observed["records"][0]["path_points_m"])
    def test_engine_returns_qualified_distance_and_unavailable_clear_width(self):
        engine=IfcQueryEngine.open(self.path);identifier=engine.resolve_entity("Origin")
        plan=m.QueryPlan(id="plan:route",request_id="request:route",scope=engine.scope(),steps=[
            m.PlanStep(id="origin",operation=m.SelectOperation(kind="select",concept_ids=[],count_policy=POLICIES["all_matches"],
                where=m.ComparePredicate(kind="compare",field=m.FieldRef(kind="entity_id",key="entity_id"),operator="eq",value=m.ReferencesValue(kind="references",entity_ids=[identifier])))),
            m.PlanStep(id="route",operation=m.RouteQueryOperation(kind="route_query",input_step_id="origin"))],outputs={"answer":"route"})
        validate_plan(plan,engine.bundle,engine.capabilities);result=engine.execute(plan)
        self.assertEqual(result.status,"partial",result.model_dump_json(indent=2));validate_result(result,engine.bundle,plan)
        row=result.claims[0].value.rows[0]
        self.assertIsInstance(row["distance"],m.QuantityValue);self.assertIsInstance(row["sampled_clearance"],m.UnavailableValue)
        evidence=next(n for n in result.calculations if n.plan_step_id=="route").route_evidence[0]
        self.assertEqual(evidence.metadata["source_sha256"],file_sha256(self.path));self.assertFalse(evidence.metadata["certified_emergency_route"])

if __name__=="__main__":unittest.main()
