
def flowmeter_pulse_handler:
    # check if pulse was awaited for
    on_hold_entries = []
    for on_hold in OnHold.objects.all():
        if on_hold.is_awaiting(instance):
            on_hold_entries.append(on_hold)

    # pulse was awaited for
    ignore_zones_ids = set()
    if len(on_hold_entries) > 0:
        for on_hold in on_hold_entries:
            if pulse_time == on_hold.time:
                late_pulse = False
                on_hold.current_pulses_arrived += 1
                ignore_zones_ids.add(on_hold.zone.id)  # only ignore zone if pulse is current
                on_hold.save()
            else:
                late_pulse = True
                on_hold.past_pulses_arrived += 1
                on_hold.save()

            if on_hold.missing_pulses() == 0:
                if late_pulse:
                    lg.info(f"Consumption Records @({pulse_time.strftime(settings.VERBOSE_DATETIME_FORMAT)}) for zone ({on_hold.zone}) are being updated on arrival of pulse ({instance!r})")
                    update_analytics(on_hold.zone, period_start=pulse_time, period_end=on_hold.time)
                else:
                    lg.info(f"Consumption Records @({pulse_time.strftime(settings.VERBOSE_DATETIME_FORMAT)}) for zone ({on_hold.zone}) are being updated on arrival of pulse ({instance!r})")
                    update_analytics(on_hold.zone, period_start=pulse_time - dt.timedelta(minutes=15), period_end=pulse_time)
                on_hold.delete()

    # now check if pulse will wait for other pulses
    other_related_zones = list(filter(lambda zone: zone is not None and zone.id not in ignore_zones_ids,
                                      (instance.meter.input_for, instance.meter.output_for)))
    for related_zone in other_related_zones:
        on_hold = OnHold.objects.create(
            zone=related_zone,
            time=pulse_time,
            ready_on=related_zone.len_active_meters(),
            current_pulses_arrived=1,
            past_pulses_arrived=Pulse.objects.filter(
                Q(meter__input_for=related_zone) | Q(meter__output_for=related_zone),
                time=pulse_time - dt.timedelta(minutes=15)).count()
        )
        if on_hold.missing_pulses() == 0:
            lg.info(f"Consumption Records @({pulse_time.strftime(settings.VERBOSE_DATETIME_FORMAT)}) for zone ({on_hold.zone}) are being updated on arrival of pulse ({instance!r})")
            update_analytics(related_zone, period_start=pulse_time - dt.timedelta(minutes=15), period_end=pulse_time)
            on_hold.delete()