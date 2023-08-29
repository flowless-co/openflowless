import datetime as dt
from celery import shared_task


@shared_task
def label_anomalies(day: str):
    import pandas as pd
    from adtk.detector import PersistAD
    from adtk.visualization import plot
    from fl_meters.models import Meter, Pulse
    from django.utils.dateparse import parse_date

    day = parse_date(day)

    since = dt.datetime.combine(day, dt.time(0, 15))
    until = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min)

    for meter in Meter.objects.all():
        meter_pulses = Pulse.objects.filter(meter=meter, time__gte=since, time__lte=until)

        if len(meter_pulses) == 0:
            continue

        df = pd.DataFrame(
            zip(
                [pulse.time for pulse in meter_pulses],
                [float(pulse.normalized_reading) for pulse in meter_pulses]
            ),
            columns=['time', 'reading']
        )

        df = df.set_index('time')

        # resample time series (gap-filling / aggregation)
        resampler = df.resample('15min')
        df = resampler.interpolate()
        df['reading'] = df['reading'].diff().map(lambda x: round(x, 3))

        persist_ad = PersistAD()
        persist_ad.factor_year = 7
        anomalies = persist_ad.fit_detect(df)

        pulses_to_update = []
        for anomaly in anomalies.iterrows():
            if anomaly[1][0] == 1:
                date = anomaly[0]
                pulse_lookup = filter(lambda pulse: pulse.time == date, meter_pulses)
                try:
                    found_pulse = next(pulse_lookup)
                    found_pulse.anomaly = True
                    pulses_to_update.append(found_pulse)
                except StopIteration:
                    pass

        x = 1
        if x == 2:
            Pulse.objects.bulk_update(pulses_to_update, ['anomaly'])

        plot(df, anomaly=anomalies, anomaly_color='red', anomaly_tag='marker')

    print()


