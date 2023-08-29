from .models import PressurePulse, Pulse

ignore_meter = []

def on_pressure_sensor(pulse: PressurePulse):
    return True

def on_flow_meter(pulse: Pulse):
    return True
