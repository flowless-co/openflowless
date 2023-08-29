from collections import defaultdict
from functools import reduce

import pytz
from django.test import TestCase

from fl_meters.models import *
from fl_meters.signals import get_offset_time

def setup_zones(self):
    self.red = Zone.objects.create(name='red')
    self.yellow = Zone.objects.create(name='yellow')
    self.white = Zone.objects.create(name='white')
    self.blue = Zone.objects.create(name='blue')

def setup_flow_meters(self):
    mm = MeterModel.objects.create(manufacturer='', model_number='', digits=6)

    self.mtr1 = Meter.objects.create(meter_model=mm, input_for=self.red)
    self.mtr2 = Meter.objects.create(meter_model=mm, input_for=self.yellow, output_for=self.red)
    self.mtr3 = Meter.objects.create(meter_model=mm, input_for=self.white, output_for=self.yellow)
    self.mtr4 = Meter.objects.create(meter_model=mm, input_for=self.blue, reading_factor=2, reading_offset=17)

    Pulse.objects.create(meter=self.mtr1, time=self.t515, reading=360)
    Pulse.objects.create(meter=self.mtr2, time=self.t515, reading=220)
    Pulse.objects.create(meter=self.mtr3, time=self.t515, reading=40)
    Pulse.objects.create(meter=self.mtr4, time=self.t515, reading=30)


def setup_db_pressure_transmitter(self):
    tm = TransmitterModel.objects.create(manufacturer='', model_number='')

    # zone `red` has two azp-cooperating pressure transmitters
    self.ptm1 = PressureTransmitter.objects.create(meter_model=tm)
    self.ptm2 = PressureTransmitter.objects.create(meter_model=tm)
    ZoneHasPressureTransmitter.objects.create(zone=self.red, use_for_azp=True, transmitter=self.ptm1)
    ZoneHasPressureTransmitter.objects.create(zone=self.red, use_for_azp=True, transmitter=self.ptm2)

    # zone `yellow` has only one azp pressure transmitter
    self.ptm3 = PressureTransmitter.objects.create(meter_model=tm)
    ZoneHasPressureTransmitter.objects.create(zone=self.yellow, use_for_azp=True, transmitter=self.ptm3)

    # zone `white` has only one azp pressure transmitter
    self.ptm4 = PressureTransmitter.objects.create(meter_model=tm)
    ZoneHasPressureTransmitter.objects.create(zone=self.white, use_for_azp=True, transmitter=self.ptm4)


def make_t(n_years=None, n_months=None, n_days=None, hours_each_day=None):
    if hours_each_day is None:
        hours_each_day = [0, 1, 23]
    if n_days is None:
        n_days = [1, 2]
    if n_months is None:
        n_months = [3]
    if n_years is None:
        n_years = [2020]

    return_dict = defaultdict(lambda: defaultdict(dict))

    for day in n_days:
        day_obj = return_dict[str(day)]
        for hour in hours_each_day:
            for interval in [0, 15, 30, 45]:
                day_obj[str(hour)][str(interval)] = dt.datetime(year=2020, month=3, day=5, hour=hour, minute=interval, tzinfo=utc)

    return return_dict


def transmission_setup_db(self):
    mm = MeterModel.objects.create(manufacturer='', model_number='', digits=6)
    self.tsm1 = TransmissionLine.objects.create()
    self.tsm2 = TransmissionLine.objects.create()

    self.mtr11 = Meter.objects.create(meter_model=mm, tsm_input=self.tsm1)
    self.mtr12 = Meter.objects.create(meter_model=mm, tsm_output=self.tsm1, tsm_input=self.tsm2)
    self.mtr13 = Meter.objects.create(meter_model=mm, tsm_output=self.tsm2)

    Pulse.objects.create(meter=self.mtr11, time=self.t['day1'][0][15], reading=120)
    Pulse.objects.create(meter=self.mtr12, time=self.t['day1'][0][15], reading=120)
    Pulse.objects.create(meter=self.mtr13, time=self.t['day1'][0][15], reading=100)
    OnHold.objects.all().delete()


class ConfigurationTestSuit(TestCase):
    def test_config_files_exist(self):
        local_settings_js = os.path.join(settings.STATIC_ROOT, 'fl_dashboard', 'js', 'local_settings.js')
        dashboard_customization = os.path.join(settings.BASE_DIR, 'fl_dashboard', 'customization.py')
        self.assertTrue(os.path.exists(local_settings_js))
        self.assertTrue(os.path.exists(dashboard_customization))


class OnHoldEntries(TestCase):
    red: Zone = None
    yellow: Zone = None
    white: Zone = None
    mtr1: Meter = None
    mtr2: Meter = None
    mtr3: Meter = None
    mtr4: Meter = None
    t515 = dt.datetime(year=2020, month=3, day=5, hour=17, minute=15, tzinfo=utc)
    t530 = t515 + dt.timedelta(minutes=15)
    # mtr1 >  RED  > mtr2 >  YELLOW  > mtr3 >  BLUE
    # mtr4 > WHITE

    def setUp(self):
        setup_zones(self)
        setup_flow_meters(self)

    def test_pulses_are_being_held_in_onhold_table(self):
        Pulse.objects.create(meter=self.mtr1, time=self.t530, reading=150)
        self.assertEqual(OnHold.objects.filter(zone=self.red, time=self.t530).count(), 1)

    def test_onhold_entries_have_correct_ready_on_values(self):
        on_hold_entry = OnHold.objects.get(zone=self.red, time=self.t515)
        self.assertEqual(on_hold_entry.ready_on, 2)

    def test_onhold_entries_have_correct_arrived_values(self):
        on_hold_entry = OnHold.objects.get(zone=self.red, time=self.t515)
        self.assertEqual(on_hold_entry.past_pulses_arrived, 0)
        self.assertEqual(on_hold_entry.current_pulses_arrived, 2)

    def test_onhold_entries_count_missing_pulses_correctly(self):
        on_hold_entry = OnHold.objects.get(zone=self.red, time=self.t515)
        self.assertEqual(on_hold_entry.missing_pulses(), 2)

    def test_onhold_entries_catch_awaiting_past_pulses(self):
        on_hold_entry = OnHold.objects.get(zone=self.red, time=self.t515)
        past_pulse = Pulse.objects.create(meter=self.mtr1, time=self.t515 - dt.timedelta(minutes=15), reading=5)
        self.assertTrue(on_hold_entry.is_awaiting(past_pulse))

    def test_onhold_entries_catch_awaiting_current_pulses(self):
        current_pulse = Pulse.objects.create(meter=self.mtr1, time=self.t530, reading=150)
        on_hold_entry = OnHold.objects.get(zone=self.red, time=self.t530)
        self.assertTrue(on_hold_entry.is_awaiting(current_pulse))

    def test_onhold_entries_dont_catch_unrelated_pulses(self):
        current_pulse = Pulse.objects.create(meter=self.mtr1, time=self.t530, reading=150)
        on_hold_entry = OnHold.objects.get(zone=self.red, time=self.t515)
        self.assertFalse(on_hold_entry.is_awaiting(current_pulse))

class FlowMeterAnalysis(TestCase):
    red: Zone = None
    yellow: Zone = None
    white: Zone = None
    blue: Zone = None
    mtr1: Meter = None
    mtr2: Meter = None
    mtr3: Meter = None
    mtr4: Meter = None
    tsm1: TransmissionLine = None
    tsm2: TransmissionLine = None
    mtr11: Meter = None
    mtr12: Meter = None
    mtr13: Meter = None
    t515 = dt.datetime(year=2020, month=3, day=5, hour=17, minute=15, tzinfo=utc)
    t530 = t515 + dt.timedelta(minutes=15)
    t545 = t530 + dt.timedelta(minutes=15)
    # mtr1 >  RED  > mtr2 >  YELLOW  > mtr3 >  BLUE
    # mtr4 > WHITE

    def setUp(self):
        setup_zones(self)
        setup_flow_meters(self)

    def test_qh_consumption_for_singular_zone(self):
        """ 5:30 MTR4 """
        Pulse.objects.create(meter=self.mtr4, time=self.t530, reading=45)
        qh_entry = QuarterHourlyZoneConsumption.objects.get(zone_id=self.blue, datetime=self.t530)
        self.assertNotEqual(qh_entry.consumption, 15,
                            "Reading factor and reading offset aren't being taken into consideration")
        self.assertEqual(qh_entry.consumption, 30,
                         "New Pulse doesn't calculate period's consumption properly.")

    def test_qh_consumption_for_singular_zone_if_a_pulse_arrives_late(self):
        """ 5:45 MTR4 , 5:30 MTR4 """
        Pulse.objects.create(meter=self.mtr4, time=self.t545, reading=70)

        self.assertRaises(QuarterHourlyZoneConsumption.DoesNotExist,
                          QuarterHourlyZoneConsumption.objects.get, zone_id=self.blue, datetime=self.t545)

        on_hold = OnHold.objects.get(zone=self.blue, time=self.t545)
        self.assertEqual(on_hold.ready_on, 1)
        self.assertEqual(on_hold.missing_pulses(), 1)

        # late pulse arrives:
        Pulse.objects.create(meter=self.mtr4, time=self.t530, reading=45)
        qh_entry_530 = QuarterHourlyZoneConsumption.objects.get(zone_id=self.blue, datetime=self.t530)
        qh_entry_545 = QuarterHourlyZoneConsumption.objects.get(zone_id=self.blue, datetime=self.t545)
        self.assertEqual(qh_entry_530.consumption, 30)
        self.assertEqual(qh_entry_545.consumption, 50)

        # OnHold entries should be deleted by now
        self.assertRaises(OnHold.DoesNotExist, OnHold.objects.get, zone=self.blue, time=self.t545)
        self.assertRaises(OnHold.DoesNotExist, OnHold.objects.get, zone=self.blue, time=self.t530)

    def test_qh_consumption_if_pulses_dont_arrive_in_order(self):
        """ 5:30 MTR1 , 5:30 MTR3 , 5:30 MTR2 """
        Pulse.objects.create(meter=self.mtr1, time=self.t530, reading=720)
        Pulse.objects.create(meter=self.mtr3, time=self.t530, reading=80)
        red_on_hold = OnHold.objects.get(zone=self.red, time=self.t530)
        yellow_on_hold = OnHold.objects.get(zone=self.yellow, time=self.t530)

        # Both zones are missing Eclair's t530 Pulse
        self.assertEqual(red_on_hold.missing_pulses(), 1, "Wrong missing pulses on OnHold entry")
        self.assertEqual(yellow_on_hold.missing_pulses(), 1, "Wrong missing pulses on OnHold entry")

        Pulse.objects.create(meter=self.mtr2, time=self.t530, reading=440)

        # Check actual consumption values:
        self.assertEqual(QuarterHourlyZoneConsumption.objects.get(zone_id=self.red, datetime=self.t530).consumption, 140)
        self.assertEqual(QuarterHourlyZoneConsumption.objects.get(zone_id=self.yellow, datetime=self.t530).consumption, 180)
        self.assertEqual(QuarterHourlyZoneConsumption.objects.get(zone_id=self.white, datetime=self.t530).consumption, 40)

        # OnHolds should've been deleted by now:
        self.assertFalse(OnHold.objects.filter(zone=self.red, time=self.t530).exists())
        self.assertFalse(OnHold.objects.filter(zone=self.yellow, time=self.t530).exists())
        self.assertFalse(OnHold.objects.filter(zone=self.white, time=self.t530).exists())

    def test_qh_consumption_when_a_pulse_arrives_late(self):
        # 5:30 Pulses
        Pulse.objects.create(meter=self.mtr1, time=self.t530, reading=720)
        Pulse.objects.create(meter=self.mtr3, time=self.t530, reading=80)
        # 5:45 Pulses
        Pulse.objects.create(meter=self.mtr1, time=self.t545, reading=840)
        Pulse.objects.create(meter=self.mtr2, time=self.t545, reading=490)
        Pulse.objects.create(meter=self.mtr3, time=self.t545, reading=90)

        # 4 OnHold entries all waiting for MTR2's 5:30
        self.assertEqual(OnHold.objects.filter(zone=self.red, time__gte=self.t530).count(), 2)
        self.assertEqual(OnHold.objects.filter(zone=self.yellow, time__gte=self.t530).count(), 2)

        # Late arrival of MTR2's 5:30 pulse
        Pulse.objects.create(meter=self.mtr2, time=self.t530, reading=440)

        # expected qh_entries:
        entries = {
            QuarterHourlyZoneConsumption.objects.get(zone_id=self.red, datetime=self.t530): 140,
            QuarterHourlyZoneConsumption.objects.get(zone_id=self.red, datetime=self.t545): 70,
            QuarterHourlyZoneConsumption.objects.get(zone_id=self.yellow, datetime=self.t530): 180,
            QuarterHourlyZoneConsumption.objects.get(zone_id=self.yellow, datetime=self.t545): 40,
            QuarterHourlyZoneConsumption.objects.get(zone_id=self.white, datetime=self.t530): 40,
            QuarterHourlyZoneConsumption.objects.get(zone_id=self.white, datetime=self.t545): 10
        }
        for qh_entry, expected_value in entries.items():
            self.assertEqual(qh_entry.consumption, expected_value)


class TransmissionPulsesOnHoldTests(TestCase):
    tsm1: TransmissionLine = None
    tsm2: TransmissionLine = None
    mtr11: Meter = None
    mtr12: Meter = None
    mtr13: Meter = None
    t = {
        'day1': {
            0: {
                0: dt.datetime(year=2020, month=3, day=5, hour=0, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=5, hour=0, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=5, hour=0, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=5, hour=0, minute=45, tzinfo=utc),
            },
            1: {
                0: dt.datetime(year=2020, month=3, day=5, hour=1, minute=0, tzinfo=utc),
                15:  dt.datetime(year=2020, month=3, day=5, hour=1, minute=15, tzinfo=utc),
                30:  dt.datetime(year=2020, month=3, day=5, hour=1, minute=30, tzinfo=utc),
                45:  dt.datetime(year=2020, month=3, day=5, hour=1, minute=45, tzinfo=utc),
            },
            23: {
                0: dt.datetime(year=2020, month=3, day=5, hour=23, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=5, hour=23, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=5, hour=23, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=5, hour=23, minute=45, tzinfo=utc),
            }
        },
        'day2': {
            0: {
                0: dt.datetime(year=2020, month=3, day=6, hour=0, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=0, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=0, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=0, minute=45, tzinfo=utc),
            },
            1: {
                0: dt.datetime(year=2020, month=3, day=6, hour=1, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=1, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=1, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=1, minute=45, tzinfo=utc),
            },
            23: {
                0: dt.datetime(year=2020, month=3, day=6, hour=23, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=23, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=23, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=23, minute=45, tzinfo=utc),
            }
        }
    }

    def setUp(self):
        transmission_setup_db(self)

    def test_is_awaiting(self):
        # >2 d1-0100
        # AWAITS:
        # d1-0045 (13)  # past pulse
        # IGNORES:
        # d1-0100 (12)  # different meter
        # d1-0115 (13)  # future pulse
        # d1-0015 (13)  # kickoff pulse (conflict assertion)
        # d2-0000 (13)  # closure pulse (conflict assertion)

        onhold = OnHold(transmission_line=self.tsm2, time=self.t['day1'][1][0], ready_on=1)

        past_pulse = Pulse(meter=self.mtr13, time=self.t['day1'][0][45])
        self.assertTrue(onhold.is_awaiting(past_pulse))

        different_meter = Pulse(meter=self.mtr11, time=self.t['day1'][1][0])
        self.assertFalse(onhold.is_awaiting(different_meter))

        future_pulse = Pulse(meter=self.mtr13, time=self.t['day1'][1][15])
        self.assertFalse(onhold.is_awaiting(future_pulse))

        kickoff_pulse = Pulse(meter=self.mtr13, time=self.t['day1'][0][15])
        self.assertFalse(onhold.is_awaiting(kickoff_pulse))

        closure_pulse = Pulse(meter=self.mtr13, time=self.t['day2'][0][0])
        self.assertFalse(onhold.is_awaiting(closure_pulse))

        # T2 d1
        # AWAITS:
        # d2-0000 (12)  # current input
        # d1-0015 (12)  # past input
        # d1-0015 (13)  # past output
        # IGNORES:
        # d2-0000 (11)  # different meter
        # d2-0015 (13)  # future pulse
        # d1-0030 (13)  # intermittent pulse
        # d1-2345 (13)  # 15-minute past pulse (conflict assertion)

        onhold = OnHold(transmission_line=self.tsm2, time=self.t['day1'][0][0], ready_on=2)

        current_input = Pulse(meter=self.mtr12, time=self.t['day2'][0][0])
        self.assertTrue(onhold.is_awaiting(current_input))

        past_input = Pulse(meter=self.mtr12, time=self.t['day1'][0][15])
        self.assertTrue(onhold.is_awaiting(past_input))

        past_output = Pulse(meter=self.mtr13, time=self.t['day1'][0][15])
        self.assertTrue(onhold.is_awaiting(past_output))

        different_meter = Pulse(meter=self.mtr11, time=self.t['day2'][0][0])
        self.assertFalse(onhold.is_awaiting(different_meter))

        future_pulse = Pulse(meter=self.mtr13, time=self.t['day2'][0][15])
        self.assertFalse(onhold.is_awaiting(future_pulse))

        intermittent_pulse = Pulse(meter=self.mtr13, time=self.t['day1'][0][30])
        self.assertFalse(onhold.is_awaiting(intermittent_pulse))

        past_15_pulse = Pulse(meter=self.mtr13, time=self.t['day2'][23][45])
        self.assertFalse(onhold.is_awaiting(past_15_pulse))

    def test_scenario_pulses_in_order(self):
        before = OnHold.objects.count()

        Pulse.objects.create(meter=self.mtr11, time=self.t['day1'][0][30], reading=170)
        self.assertEqual(before, OnHold.objects.count())
        Pulse.objects.create(meter=self.mtr12, time=self.t['day1'][0][30], reading=170)
        self.assertEqual(before, OnHold.objects.count())
        Pulse.objects.create(meter=self.mtr13, time=self.t['day1'][0][30], reading=140)
        self.assertEqual(before, OnHold.objects.count())

        Pulse.objects.create(meter=self.mtr11, time=self.t['day1'][23][45], reading=1200)
        self.assertEqual(before, OnHold.objects.count())
        Pulse.objects.create(meter=self.mtr12, time=self.t['day1'][23][45], reading=1200)
        self.assertEqual(OnHold.tsm_inflow(self.tsm1, self.t['day1'][23][45]).count(), 1)
        Pulse.objects.create(meter=self.mtr13, time=self.t['day1'][23][45], reading=820)
        self.assertEqual(OnHold.tsm_inflow(self.tsm2, self.t['day1'][23][45]).count(), 1)

        before = OnHold.objects.count()

        Pulse.objects.create(meter=self.mtr11, time=self.t['day2'][0][0], reading=1250)
        onhold = OnHold.tsm_loss(self.tsm1, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)

        Pulse.objects.create(meter=self.mtr12, time=self.t['day2'][0][0], reading=1250)
        self.assertEqual(OnHold.tsm_loss(self.tsm1, self.t['day1'][0][0]).count(), 0)  # past on hold should be cleared
        onhold = OnHold.tsm_loss(self.tsm2, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)

        Pulse.objects.create(meter=self.mtr13, time=self.t['day2'][0][0], reading=1250)
        self.assertEqual(OnHold.tsm_loss(self.tsm2, self.t['day1'][0][0]).count(), 0)  # past on hold should be cleared

    def test_scenario_pulses_late(self):
        OnHold.objects.all().delete()
        Pulse.objects.all().delete()

        # In-order Pulses
        Pulse.objects.create(meter=self.mtr13, time=self.t['day1'][0][15], reading=100)
        onhold = OnHold.tsm_inflow(self.tsm2, self.t['day1'][0][15])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)

        Pulse.objects.create(meter=self.mtr11, time=self.t['day2'][0][0], reading=1250)
        onhold = OnHold.tsm_loss(self.tsm1, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 3)

        Pulse.objects.create(meter=self.mtr12, time=self.t['day2'][0][0], reading=1250)
        onhold = OnHold.tsm_inflow(self.tsm1, self.t['day2'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)
        onhold = OnHold.tsm_loss(self.tsm1, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 2)
        onhold = OnHold.tsm_loss(self.tsm2, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 2)

        Pulse.objects.create(meter=self.mtr13, time=self.t['day2'][0][0], reading=800)
        onhold = OnHold.tsm_inflow(self.tsm2, self.t['day2'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)
        onhold = OnHold.tsm_loss(self.tsm2, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)

        # Late Pulses:
        Pulse.objects.create(meter=self.mtr12, time=self.t['day1'][0][15], reading=120)
        onhold = OnHold.tsm_inflow(self.tsm1, self.t['day1'][0][15])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)
        onhold = OnHold.tsm_loss(self.tsm1, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)
        onhold = OnHold.tsm_loss(self.tsm2, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 0)

        Pulse.objects.create(meter=self.mtr11, time=self.t['day1'][0][15], reading=120)
        onhold = OnHold.tsm_loss(self.tsm1, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 0)

    def test_scenario_pulses_late_v2(self):
        OnHold.objects.all().delete()
        Pulse.objects.all().delete()

        # In-order Pulses
        Pulse.objects.create(meter=self.mtr11, time=self.t['day1'][0][15], reading=120)
        self.assertEqual(OnHold.objects.all().count(), 0)

        Pulse.objects.create(meter=self.mtr13, time=self.t['day1'][0][15], reading=100)
        onhold = OnHold.tsm_inflow(self.tsm2, self.t['day1'][0][15])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)

        Pulse.objects.create(meter=self.mtr11, time=self.t['day2'][0][0], reading=1250)
        onhold = OnHold.tsm_loss(self.tsm1, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 2)

        Pulse.objects.create(meter=self.mtr13, time=self.t['day2'][0][0], reading=800)
        onhold = OnHold.tsm_inflow(self.tsm2, self.t['day2'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)
        onhold = OnHold.tsm_loss(self.tsm2, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 2)

        Pulse.objects.create(meter=self.mtr12, time=self.t['day2'][0][0], reading=1250)
        onhold = OnHold.tsm_inflow(self.tsm1, self.t['day2'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)
        onhold = OnHold.tsm_loss(self.tsm1, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)
        onhold = OnHold.tsm_loss(self.tsm2, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)

        # Late Pulses:
        Pulse.objects.create(meter=self.mtr12, time=self.t['day1'][0][15], reading=120)
        onhold = OnHold.tsm_inflow(self.tsm1, self.t['day1'][0][15])
        self.assertEqual(len(onhold), 1)
        self.assertEqual(onhold[0].missing_pulses(), 1)
        onhold = OnHold.tsm_loss(self.tsm1, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 0)
        onhold = OnHold.tsm_loss(self.tsm2, self.t['day1'][0][0])
        self.assertEqual(len(onhold), 0)

    def test_missing_meters(self):
        self.mtr11.tsm_input = None
        self.mtr11.save()
        self.mtr12.tsm_input = None
        self.mtr12.save()
        self.mtr13.tsm_output = None
        self.mtr13.save()

        before = OnHold.objects.count()
        Pulse.objects.create(meter=self.mtr12, time=self.t['day2'][0][0], reading=1250)
        self.assertEqual(OnHold.objects.count(), before + 1)

class TransmissionPulsesAnalysisTests(TestCase):
    tsm1: TransmissionLine = None
    tsm2: TransmissionLine = None
    mtr11: Meter = None
    mtr12: Meter = None
    mtr13: Meter = None
    t = {
        'day1': {
            0: {
                0: dt.datetime(year=2020, month=3, day=5, hour=0, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=5, hour=0, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=5, hour=0, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=5, hour=0, minute=45, tzinfo=utc),
            },
            1: {
                0: dt.datetime(year=2020, month=3, day=5, hour=1, minute=0, tzinfo=utc),
                15:  dt.datetime(year=2020, month=3, day=5, hour=1, minute=15, tzinfo=utc),
                30:  dt.datetime(year=2020, month=3, day=5, hour=1, minute=30, tzinfo=utc),
                45:  dt.datetime(year=2020, month=3, day=5, hour=1, minute=45, tzinfo=utc),
            },
            23: {
                0: dt.datetime(year=2020, month=3, day=5, hour=23, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=5, hour=23, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=5, hour=23, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=5, hour=23, minute=45, tzinfo=utc),
            }
        },
        'day2': {
            0: {
                0: dt.datetime(year=2020, month=3, day=6, hour=0, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=0, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=0, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=0, minute=45, tzinfo=utc),
            },
            1: {
                0: dt.datetime(year=2020, month=3, day=6, hour=1, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=1, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=1, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=1, minute=45, tzinfo=utc),
            },
            23: {
                0: dt.datetime(year=2020, month=3, day=6, hour=23, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=23, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=23, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=23, minute=45, tzinfo=utc),
            }
        }
    }

    def check_inflow_records(self, tsm, pulse_time, consumption):
        last_consumption = consumption[len(consumption)-1]
        consumption += [last_consumption for i in range(4 - len(consumption))]

        offset_day = get_offset_time(pulse_time).date()

        self.assertEqual(QuarterHourlyTSMInflow.objects.get(transmission_line=tsm, datetime=pulse_time).consumption, consumption[0])
        self.assertEqual(DailyTSMInflow.objects.get(transmission_line=tsm, date=offset_day).consumption, consumption[1])
        self.assertEqual(MonthlyTSMInflow.objects.get(transmission_line=tsm, date=offset_day.replace(day=1)).consumption, consumption[2])
        self.assertEqual(YearlyTSMInflow.objects.get(transmission_line=tsm, year=offset_day.year).consumption, consumption[3])

    def check_loss_records(self, tsm, loss_day, loss):
        last_loss = loss[len(loss)-1]
        loss += [last_loss for i in range(3 - len(loss))]

        self.assertEqual(DailyTSMLossRecord.objects.get(transmission_line=tsm, date=loss_day).loss, loss[0])
        self.assertEqual(MonthlyTSMLossRecord.objects.get(transmission_line=tsm, date=loss_day.replace(day=1)).loss, loss[1])
        self.assertEqual(YearlyTSMLossRecord.objects.get(transmission_line=tsm, year=loss_day.year).loss, loss[2])

    def setUp(self):
        transmission_setup_db(self)

    def test_scenario_in_order(self):
        before = QuarterHourlyTSMInflow.objects.all().count()
        Pulse.objects.create(meter=self.mtr11, time=self.t['day1'][0][30], reading=170)
        # check no records created for pulses that are missing past pulses
        self.assertEqual(before, QuarterHourlyTSMInflow.objects.all().count())

        Pulse.objects.create(meter=self.mtr12, time=self.t['day1'][0][30], reading=170)
        self.check_inflow_records(self.tsm1, self.t['day1'][0][30], [50])

        Pulse.objects.create(meter=self.mtr13, time=self.t['day1'][0][30], reading=140)
        self.check_inflow_records(self.tsm2, self.t['day1'][0][30], [40])

        Pulse.objects.create(meter=self.mtr11, time=self.t['day1'][23][45], reading=1200)
        Pulse.objects.create(meter=self.mtr12, time=self.t['day1'][23][45], reading=1200)
        Pulse.objects.create(meter=self.mtr13, time=self.t['day1'][23][45], reading=820)
        # check no records created for pulses that are missing past pulses
        self.assertEqual(QuarterHourlyTSMInflow.objects.filter(transmission_line=self.tsm1, datetime=self.t['day1'][23][45]).count(), 0)
        self.assertEqual(QuarterHourlyTSMInflow.objects.filter(transmission_line=self.tsm2, datetime=self.t['day1'][23][45]).count(), 0)

        Pulse.objects.create(meter=self.mtr11, time=self.t['day2'][0][0], reading=1250)
        # check records haven't been created for for input pulses
        self.assertEqual(QuarterHourlyTSMInflow.objects.filter(transmission_line=self.tsm1, datetime=self.t['day2'][0][0]).count(), 0)

        Pulse.objects.create(meter=self.mtr12, time=self.t['day2'][0][0], reading=1250)
        self.check_inflow_records(self.tsm1, self.t['day2'][0][0], [50, 100])
        self.check_loss_records(self.tsm1, self.t['day1'][0][0], [0])

        # check records haven't been created for for input pulses
        self.assertEqual(DailyTSMInflow.objects.filter(transmission_line=self.tsm1, date=self.t['day2'][0][0]).count(), 0)
        self.assertEqual(MonthlyTSMInflow.objects.filter(transmission_line=self.tsm1, date=self.t['day1'][0][0].replace(day=1)).count(), 1)

        Pulse.objects.create(meter=self.mtr13, time=self.t['day2'][0][0], reading=890)
        self.check_inflow_records(self.tsm2, self.t['day2'][0][0], [70, 110])
        self.check_loss_records(self.tsm2, self.t['day1'][0][0], [340])

        # check future record hasn't been created for end-of-day pulse
        self.assertEqual(DailyTSMInflow.objects.filter(transmission_line=self.tsm2, date=self.t['day2'][0][0]).count(), 0)
        self.assertEqual(MonthlyTSMInflow.objects.filter(transmission_line=self.tsm2, date=self.t['day1'][0][0].replace(day=1)).count(), 1)

    def test_scenario_late(self):
        self.assertEqual(QuarterHourlyTSMInflow.objects.count(), 0)
        self.assertEqual(DailyTSMInflow.objects.count(), 0)
        self.assertEqual(MonthlyTSMInflow.objects.count(), 0)
        self.assertEqual(YearlyTSMInflow.objects.count(), 0)

        Pulse.objects.create(meter=self.mtr12, time=self.t['day1'][0][30], reading=170)
        self.check_inflow_records(self.tsm1, self.t['day1'][0][30], [50])

        Pulse.objects.create(meter=self.mtr11, time=self.t['day1'][23][45], reading=1200)
        Pulse.objects.create(meter=self.mtr13, time=self.t['day1'][23][45], reading=820)
        # check these two pulses didn't create any inflow records
        self.assertEqual(QuarterHourlyTSMInflow.objects.count(), 1)
        self.assertEqual(DailyTSMInflow.objects.count(), 1)
        self.assertEqual(MonthlyTSMInflow.objects.count(), 1)
        self.assertEqual(YearlyTSMInflow.objects.count(), 1)

        Pulse.objects.create(meter=self.mtr13, time=self.t['day2'][0][0], reading=890)
        self.check_inflow_records(self.tsm2, self.t['day2'][0][0], [70])

        Pulse.objects.create(meter=self.mtr11, time=self.t['day2'][0][0], reading=1250)
        # check pulse didn't create any inflow records
        self.assertEqual(QuarterHourlyTSMInflow.objects.count(), 2)
        self.assertEqual(DailyTSMInflow.objects.count(), 2)
        self.assertEqual(MonthlyTSMInflow.objects.count(), 2)
        self.assertEqual(YearlyTSMInflow.objects.count(), 2)

        Pulse.objects.create(meter=self.mtr12, time=self.t['day2'][0][0], reading=1250)
        self.check_loss_records(self.tsm1, self.t['day1'][0][0], [0])
        self.check_loss_records(self.tsm2, self.t['day1'][0][0], [340])

        # late d1-23:45 pulse fulfills d2-00:00 pulse inflow records
        Pulse.objects.create(meter=self.mtr12, time=self.t['day1'][23][45], reading=1200)
        self.check_inflow_records(self.tsm1, self.t['day2'][0][0], [50, 100])

        Pulse.objects.create(meter=self.mtr13, time=self.t['day1'][0][30], reading=140)
        self.check_inflow_records(self.tsm2, self.t['day1'][0][30], [40, 110])

    def test_missing_meters(self):
        self.mtr11.tsm_input = None
        self.mtr11.save()
        self.mtr12.tsm_input = None
        self.mtr12.save()
        self.mtr13.tsm_output = None
        self.mtr13.save()

        Pulse.objects.create(meter=self.mtr12, time=self.t['day1'][0][30], reading=170)
        self.check_inflow_records(self.tsm1, self.t['day1'][0][30], [50])

        Pulse.objects.create(meter=self.mtr12, time=self.t['day2'][0][0], reading=1250)
        self.assertEqual(DailyTSMLossRecord.objects.filter(transmission_line=self.tsm1, date=self.t['day1'][0][0]).count(), 0)
        self.assertEqual(MonthlyTSMLossRecord.objects.filter(transmission_line=self.tsm1, date=self.t['day1'][0][0].replace(day=1)).count(), 0)
        self.assertEqual(YearlyTSMLossRecord.objects.filter(transmission_line=self.tsm1, year=self.t['day1'][0][0].year).count(), 0)


class PressureTransmitterAnalysis(TestCase):
    red: Zone = None
    yellow: Zone = None
    white: Zone = None
    ptm1: PressureTransmitter = None
    ptm2: PressureTransmitter = None
    ptm3: PressureTransmitter = None
    ptm4: PressureTransmitter = None
    t = {
        'day1': {
            0: {
                0: dt.datetime(year=2020, month=3, day=5, hour=0, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=5, hour=0, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=5, hour=0, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=5, hour=0, minute=45, tzinfo=utc),
            },
            1: {
                0: dt.datetime(year=2020, month=3, day=5, hour=1, minute=0, tzinfo=utc),
                15:  dt.datetime(year=2020, month=3, day=5, hour=1, minute=15, tzinfo=utc),
                30:  dt.datetime(year=2020, month=3, day=5, hour=1, minute=30, tzinfo=utc),
                45:  dt.datetime(year=2020, month=3, day=5, hour=1, minute=45, tzinfo=utc),
            },
            23: {
                0: dt.datetime(year=2020, month=3, day=5, hour=23, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=5, hour=23, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=5, hour=23, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=5, hour=23, minute=45, tzinfo=utc),
            }
        },
        'day2': {
            0: {
                0: dt.datetime(year=2020, month=3, day=6, hour=0, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=0, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=0, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=0, minute=45, tzinfo=utc),
            },
            1: {
                0: dt.datetime(year=2020, month=3, day=6, hour=1, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=1, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=1, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=1, minute=45, tzinfo=utc),
            },
            23: {
                0: dt.datetime(year=2020, month=3, day=6, hour=23, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=23, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=23, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=23, minute=45, tzinfo=utc),
            }
        },
        'day31': {
            0: {
                0: dt.datetime(year=2020, month=3, day=6, hour=0, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=0, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=0, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=0, minute=45, tzinfo=utc),
            },
            1: {
                0: dt.datetime(year=2020, month=3, day=6, hour=1, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=6, hour=1, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=6, hour=1, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=6, hour=1, minute=45, tzinfo=utc),
            },
            23: {
                0: dt.datetime(year=2020, month=3, day=31, hour=23, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=3, day=31, hour=23, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=3, day=31, hour=23, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=3, day=31, hour=23, minute=45, tzinfo=utc),
            }
        },
    }
    month2 = {
        'day1': {
            0: {
                0: dt.datetime(year=2020, month=4, day=1, hour=0, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=4, day=1, hour=0, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=4, day=1, hour=0, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=4, day=1, hour=0, minute=45, tzinfo=utc),
            },
            1: {
                0: dt.datetime(year=2020, month=4, day=1, hour=1, minute=0, tzinfo=utc),
                15:  dt.datetime(year=2020, month=4, day=1, hour=1, minute=15, tzinfo=utc),
                30:  dt.datetime(year=2020, month=4, day=1, hour=1, minute=30, tzinfo=utc),
                45:  dt.datetime(year=2020, month=4, day=1, hour=1, minute=45, tzinfo=utc),
            },
            23: {
                0: dt.datetime(year=2020, month=4, day=1, hour=23, minute=0, tzinfo=utc),
                15: dt.datetime(year=2020, month=4, day=1, hour=23, minute=15, tzinfo=utc),
                30: dt.datetime(year=2020, month=4, day=1, hour=23, minute=30, tzinfo=utc),
                45: dt.datetime(year=2020, month=4, day=1, hour=23, minute=45, tzinfo=utc),
            }
        },
    }

    def setUp(self):
        # zone `red` has two azp-cooperating pressure transmitters
        # zone `yellow` has only one azp pressure transmitter
        # zone `white` has no azp pressure transmitters
        setup_zones(self)
        setup_db_pressure_transmitter(self)

    def test_simple_scenario(self):
        PressurePulse.objects.create(transmitter=self.ptm1, time=self.t['day1'][0][15], reading=4)
        hourly_record = HourlyAvgZonePressure.objects.get(zone=self.red, time=self.t['day1'][0][0])
        monthly_record = MonthlyAvgZonePressure.objects.get(zone=self.red, date=self.t['day1'][0][0].date().replace(day=1))
        yearly_record = YearlyAvgZonePressure.objects.get(zone=self.red, year=self.t['day1'][0][0].year)
        self.assertEqual(hourly_record.azp, 4)
        self.assertEqual(monthly_record.azp, 4)
        self.assertEqual(yearly_record.azp, 4)

        PressurePulse.objects.create(transmitter=self.ptm2, time=self.t['day1'][0][15], reading=5.5)
        hourly_record = HourlyAvgZonePressure.objects.get(zone=self.red, time=self.t['day1'][0][0])
        monthly_record = MonthlyAvgZonePressure.objects.get(zone=self.red, date=self.t['day1'][0][0].date().replace(day=1))
        yearly_record = YearlyAvgZonePressure.objects.get(zone=self.red, year=self.t['day1'][0][0].year)
        self.assertEqual(hourly_record.azp, 4.75)
        self.assertEqual(monthly_record.azp, 4.75)
        self.assertEqual(yearly_record.azp, 4.75)

        PressurePulse.objects.create(transmitter=self.ptm2, time=self.t['day1'][23][45], reading=5)
        hourly_record = HourlyAvgZonePressure.objects.get(zone=self.red, time=self.t['day1'][23][0])
        monthly_record = MonthlyAvgZonePressure.objects.get(zone=self.red, date=self.t['day1'][0][0].date().replace(day=1))
        yearly_record = YearlyAvgZonePressure.objects.get(zone=self.red, year=self.t['day1'][0][0].year)
        self.assertEqual(hourly_record.azp, 5)
        self.assertAlmostEqual(monthly_record.azp, Decimal('4.83333'), 5)
        self.assertAlmostEqual(yearly_record.azp, Decimal('4.83333'), 5)

        PressurePulse.objects.create(transmitter=self.ptm2, time=self.t['day2'][0][0], reading=6)
        hourly_record = HourlyAvgZonePressure.objects.get(zone=self.red, time=self.t['day1'][23][0])
        monthly_record = MonthlyAvgZonePressure.objects.get(zone=self.red, date=self.t['day1'][23][0].date().replace(day=1))
        yearly_record = YearlyAvgZonePressure.objects.get(zone=self.red, year=self.t['day1'][23][0].year)
        self.assertEqual(hourly_record.azp, Decimal('5.5'))
        self.assertEqual(monthly_record.azp, Decimal('5.125'))
        self.assertEqual(yearly_record.azp, Decimal('5.125'))

        PressurePulse.objects.create(transmitter=self.ptm2, time=self.t['day2'][0][15], reading=5)
        hourly_record = HourlyAvgZonePressure.objects.get(zone=self.red, time=self.t['day2'][0][0])
        monthly_record = MonthlyAvgZonePressure.objects.get(zone=self.red, date=self.t['day2'][0][0].date().replace(day=1))
        yearly_record = YearlyAvgZonePressure.objects.get(zone=self.red, year=self.t['day2'][0][0].year)
        self.assertEqual(hourly_record.azp, Decimal('5'))
        self.assertAlmostEqual(monthly_record.azp, Decimal('5.1'), 5)
        self.assertAlmostEqual(yearly_record.azp, Decimal('5.1'), 5)

        PressurePulse.objects.create(transmitter=self.ptm2, time=self.month2['day1'][0][0], reading=4.2)
        hourly_record = HourlyAvgZonePressure.objects.get(zone=self.red, time=self.t['day31'][23][0])
        monthly_record = MonthlyAvgZonePressure.objects.get(zone=self.red, date=self.t['day31'][23][0].date().replace(day=1))
        yearly_record = YearlyAvgZonePressure.objects.get(zone=self.red, year=self.t['day31'][23][0].year)
        self.assertEqual(hourly_record.azp, Decimal('4.2'))
        self.assertAlmostEqual(monthly_record.azp, Decimal('4.95'), 5)
        self.assertAlmostEqual(yearly_record.azp, Decimal('4.95'), 5)

        PressurePulse.objects.create(transmitter=self.ptm2, time=self.month2['day1'][0][15], reading=6)
        hourly_record = HourlyAvgZonePressure.objects.get(zone=self.red, time=self.month2['day1'][0][0])
        monthly_record = MonthlyAvgZonePressure.objects.get(zone=self.red, date=self.month2['day1'][0][0].date().replace(day=1))
        yearly_record = YearlyAvgZonePressure.objects.get(zone=self.red, year=self.month2['day1'][0][0].year)
        self.assertEqual(hourly_record.azp, Decimal('6'))
        self.assertAlmostEqual(monthly_record.azp, Decimal('6'), 5)
        self.assertAlmostEqual(yearly_record.azp, Decimal('5.1'), 5)


class MNFLossAnalysis(TestCase):
    white: Zone = None
    ptm4: PressureTransmitter = None
    mtr4: Meter = None

    def setUp(self):
        # white has only one meter as an input, and only one pressure sensor azp-contributing
        self.white = Zone.objects.create(name='white')

        tm = TransmitterModel.objects.create(manufacturer='', model_number='')
        self.ptm4 = PressureTransmitter.objects.create(meter_model=tm)
        ZoneHasPressureTransmitter.objects.create(zone=self.white, use_for_azp=True, transmitter=self.ptm4)

        mm = MeterModel.objects.create(manufacturer='', model_number='', digits=6)
        self.mtr4 = Meter.objects.create(meter_model=mm, input_for=self.white)

    def test_x(self):
        consumption_values = [21.48, 16.11, 21.48, 17.9, 17.9, 19.69, 17.9, 17.9, 1.79, 1.79, 7.16, 3.58, 0, 7.16, 7.16, 7.16, 17.9, 19.69, 19.69, 19.69, 17.9, 17.9, 19.69, 16.11, 71.6, 71.6, 71.6, 75.18, 73.39, 68.02, 71.6, 68.02, 51.91, 53.7, 53.7, 51.91, 51.91, 53.7, 53.7, 53.7, 37.59, 37.59, 39.38, 39.38, 35.8, 42.96, 42.96, 41.17, 39.38, 37.59, 35.8, 32.22, 35.8, 34.01, 32.22, 37.59, 39.38, 39.38, 39.38, 42.96, 35.8, 35.8, 42.96, 39.38, 42.96, 42.96, 42.96, 44.75, 46.54, 46.54, 42.96, 42.96, 34.01, 35.8, 35.8, 34.01, 35.8, 35.8, 35.8, 39.38, 46.54, 46.54, 46.54, 50.12, 44.75, 46.54, 50.12, 46.54, 17.9, 17.9, 16.11, 17.9, 19.69, 17.9, 17.9, 21.48, 19.69, 17.9, 14.32, 14.32, 14.32, 17.9, 14.32, 17.9, 8.95, 8.95, 3.58, 3.58, 1.79, 8.95, 7.16, 1.79, 21.48]
        flow_readings = []
        acc = 0
        for q in consumption_values:
            acc += q
            flow_readings.append(acc)

        since_flow_pulses = dt.datetime(2020, 6, 15, 0, 15, 0, tzinfo=pytz.utc)
        until_flow_pulses = dt.datetime(2020, 6, 16, 4, 15, 0, tzinfo=pytz.utc)
        rie = 15
        delta = int((until_flow_pulses - since_flow_pulses).total_seconds()) // (60 * rie) + 1
        assert(len(flow_readings) == delta)

        pressure_readings = [5.41, 5.41, 5.42, 5.42, 5.42, 5.42, 5.28, 5.28, 5.34, 5.34, 5.38, 5.38, 5.39, 5.39, 5.38, 5.38, 5.37, 5.37, 5.39, 5.39, 5.36, 5.36, 5.42, 5.42]
        since_pressure_pulses = dt.datetime(2020, 6, 15, 0, 15, 0, tzinfo=pytz.utc)
        until_pressure_pulses = dt.datetime(2020, 6, 16, 0, 0, 0, tzinfo=pytz.utc)
        rie = 60
        delta = int((until_pressure_pulses - since_pressure_pulses).total_seconds()) // (60 * rie) + 1
        assert(len(pressure_readings) == delta)

        # Create all pressure pulses
        for i in range(24*4):
            pressure_reading_idx = i // 4
            pulse_time = since_pressure_pulses + dt.timedelta(minutes=15 * i)
            PressurePulse.objects.create(transmitter=self.ptm4, time=pulse_time, reading=pressure_readings[pressure_reading_idx])

        # Create all flow readings
        Pulse.objects.create(meter=self.mtr4, time=since_flow_pulses - dt.timedelta(minutes=15), reading=0)  # Rie
        for i, flow_reading in enumerate(flow_readings):
            pulse_time = since_flow_pulses + dt.timedelta(minutes=15 * i)  # Rie
            Pulse.objects.create(meter=self.mtr4, time=pulse_time, reading=flow_reading)

        a = 9



