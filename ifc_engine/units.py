"""Exact decimal conversions for the initial supported IFC unit families."""
from __future__ import annotations

from decimal import Decimal, localcontext

from contracts.models import Unit

DIMENSIONS = {
    "length": (1, 0, 0, 0, 0, 0, 0), "area": (2, 0, 0, 0, 0, 0, 0),
    "volume": (3, 0, 0, 0, 0, 0, 0), "mass": (0, 1, 0, 0, 0, 0, 0),
    "time": (0, 0, 1, 0, 0, 0, 0), "angle": (0, 0, 0, 0, 0, 0, 0),
    "ratio": (0, 0, 0, 0, 0, 0, 0), "number": (0, 0, 0, 0, 0, 0, 0),
    "mass_density": (-3, 1, 0, 0, 0, 0, 0), "thermal_conductivity": (1, 1, -3, 0, -1, 0, 0),
    "specific_heat_capacity": (2, 0, -2, 0, -1, 0, 0), "volumetric_flow_rate": (3, 0, -1, 0, 0, 0, 0),
    "mass_flow_rate": (0, 1, -1, 0, 0, 0, 0), "linear_velocity": (1, 0, -1, 0, 0, 0, 0),
    "pressure": (-1, 1, -2, 0, 0, 0, 0), "power": (2, 1, -3, 0, 0, 0, 0),
    "energy": (2, 1, -2, 0, 0, 0, 0), "temperature": (0, 0, 0, 0, 1, 0, 0),
}
UNIT_TYPES = {"LENGTHUNIT": "length", "AREAUNIT": "area", "VOLUMEUNIT": "volume",
              "MASSUNIT": "mass", "TIMEUNIT": "time", "PLANEANGLEUNIT": "angle"}
# Match compound measure semantics before substring families (MassDensity is
# not a mass, and VolumetricFlowRate is not a volume). Unsupported source units
# remain unresolved; this map alone establishes no conversion or factor.
MEASURE_KINDS = {
    "IfcMassDensityMeasure": "mass_density", "IfcThermalConductivityMeasure": "thermal_conductivity",
    "IfcSpecificHeatCapacityMeasure": "specific_heat_capacity", "IfcVolumetricFlowRateMeasure": "volumetric_flow_rate",
    "IfcMassFlowRateMeasure": "mass_flow_rate", "IfcLinearVelocityMeasure": "linear_velocity",
    "IfcPressureMeasure": "pressure", "IfcPowerMeasure": "power", "IfcEnergyMeasure": "energy",
    "IfcThermodynamicTemperatureMeasure": "temperature",
}
SI_TARGETS = {"length": "unit:m", "area": "unit:m2", "volume": "unit:m3",
              "mass": "unit:kg", "time": "unit:s", "angle": "unit:rad",
              "ratio": "unit:1", "number": "unit:1"}
PREFIXES = {"EXA": "1e18", "PETA": "1e15", "TERA": "1e12", "GIGA": "1e9",
            "MEGA": "1e6", "KILO": "1e3", "HECTO": "1e2", "DECA": "1e1",
            "DECI": "1e-1", "CENTI": "1e-2", "MILLI": "1e-3", "MICRO": "1e-6",
            "NANO": "1e-9", "PICO": "1e-12", "FEMTO": "1e-15", "ATTO": "1e-18", None: "1"}


def decimal_string(value) -> str:
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("non-finite source measurement")
    return format(number, "f")


def standard_units() -> dict[str, Unit]:
    definitions = [("m", "length", "1"), ("mm", "length", "0.001"),
                   ("cm", "length", "0.01"), ("ft", "length", "0.3048"),
                   ("m2", "area", "1"), ("mm2", "area", "0.000001"),
                   ("cm2", "area", "0.0001"), ("ft2", "area", "0.09290304"),
                   ("m3", "volume", "1"), ("mm3", "volume", "0.000000001"),
                   ("ft3", "volume", "0.028316846592"), ("kg", "mass", "1"),
                   ("s", "time", "1"), ("rad", "angle", "1"), ("1", "ratio", "1"),
                   ("%", "ratio", "0.01")]
    return {"unit:" + symbol: Unit(id="unit:" + symbol, symbol=symbol, kind="physical",
                                dimension=DIMENSIONS[kind], si_multiplier=scale)
            for symbol, kind, scale in definitions}


def source_unit(unit) -> Unit:
    """Read supported named units. Never infer area/volume from length defaults."""
    kind = UNIT_TYPES.get(getattr(unit, "UnitType", None))
    if kind is None:
        raise ValueError(f"unsupported IFC unit {unit.is_a()}")
    if unit.is_a("IfcSIUnit"):
        names = {"METRE": "length", "SQUARE_METRE": "area", "CUBIC_METRE": "volume",
                 "GRAM": "mass", "SECOND": "time", "RADIAN": "angle"}
        if names.get(unit.Name) != kind:
            raise ValueError(f"unsupported SI unit {unit.Name}")
        power = {"area": 2, "volume": 3}.get(kind, 1)
        scale = Decimal(PREFIXES[unit.Prefix]) ** power
        if kind == "mass":
            scale *= Decimal("0.001")  # IFC's gram -> SI kilogram.
        symbol = (unit.Prefix or "") + unit.Name
    elif unit.is_a("IfcConversionBasedUnit"):
        if getattr(unit, "ConversionOffset", 0):
            raise ValueError("offset units are not implemented")
        component = source_unit(unit.ConversionFactor.UnitComponent)
        if component.dimension != DIMENSIONS[kind]:
            raise ValueError("conversion unit has incompatible dimensions")
        scale = Decimal(str(unit.ConversionFactor.ValueComponent.wrappedValue)) * Decimal(component.si_multiplier)
        symbol = unit.Name
    else:
        raise ValueError(f"unsupported named unit {unit.is_a()}")
    return Unit(id=f"unit:ifc:{unit.id()}", symbol=symbol, kind="physical",
                dimension=DIMENSIONS[kind], si_multiplier=decimal_string(scale))


def convert(magnitude: str, source: Unit, target: Unit) -> Decimal:
    if source.kind != "physical" or target.kind != "physical" or source.dimension != target.dimension:
        raise ValueError("incompatible unit dimensions")
    parts = [magnitude, source.si_multiplier, source.si_offset, target.si_multiplier, target.si_offset]
    with localcontext() as context:
        context.prec = max(64, sum(len(p) for p in parts) + 32)
        return ((Decimal(magnitude) * Decimal(source.si_multiplier) + Decimal(source.si_offset)
                 - Decimal(target.si_offset)) / Decimal(target.si_multiplier))
