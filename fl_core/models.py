from django.db import models


class Watercourse(models.Model):

    class Meta:
        abstract = True


class WatercourseInputs(models.Model):
    watercourse = models.ForeignKey(to=Watercourse, on_delete=models.CASCADE, related_name='inputs_set')
    reader = models.ForeignKey(to='ReaderBase', on_delete=models.CASCADE, related_name='input_for')


class WatercourseOutputs(models.Model):
    watercourse = models.ForeignKey(to=Watercourse, on_delete=models.CASCADE, related_name='outputs_set')
    reader = models.ForeignKey(to='ReaderBase', on_delete=models.CASCADE, related_name='output_for')


class Zone(Watercourse):
    name = models.CharField(max_length=48)
    color = models.CharField(max_length=9, blank=True, default="#ff0000")

    def __str__(self):
        return self.name


class ReaderBase(models.Model):
    location = models.ForeignKey(to='', on_delete=models.PROTECT)
    operational_status = models.IntegerField()

    class Meta:
        abstract = True

    def value(self):
        return 0


# ANALYTICAL TABLES
class WatercourseQuarterHourlyConsumption(models.Model):
    watercourse = models.ForeignKey(to=Watercourse, on_delete=models.DO_NOTHING, related_name='qh_consumption_set')
    datetime = models.DateTimeField()
    consumption = models.DecimalField(max_digits=12, decimal_places=6)


class WatercourseDailyConsumption(models.Model):
    watercourse = models.ForeignKey(to=Watercourse, on_delete=models.DO_NOTHING, related_name='daily_consumption_set')
    date = models.DateField()
    consumption = models.DecimalField(max_digits=15, decimal_places=6)
    p_dawn = models.DecimalField(max_digits=15, decimal_places=6, default=0, blank=True)
    p_noon = models.DecimalField(max_digits=15, decimal_places=6, default=0, blank=True)
    p_afternoon = models.DecimalField(max_digits=15, decimal_places=6, default=0, blank=True)
    p_evening = models.DecimalField(max_digits=15, decimal_places=6, default=0, blank=True)
    p_nighttime = models.DecimalField(max_digits=15, decimal_places=6, default=0, blank=True)


class WatercourseMonthlyConsumption(models.Model):
    watercourse = models.ForeignKey(to=Watercourse, on_delete=models.DO_NOTHING, related_name='monthly_consumption_set')
    date = models.DateField()
    consumption = models.DecimalField(max_digits=18, decimal_places=6)
    billed_consumption = models.DecimalField(max_digits=18, decimal_places=6)
    p_week1 = models.DecimalField(max_digits=18, decimal_places=6, default=0, blank=True)
    p_week2 = models.DecimalField(max_digits=18, decimal_places=6, default=0, blank=True)
    p_week3 = models.DecimalField(max_digits=18, decimal_places=6, default=0, blank=True)
    p_week4 = models.DecimalField(max_digits=18, decimal_places=6, default=0, blank=True)


class WatercourseYearlyConsumption(models.Model):
    watercourse = models.ForeignKey(to=Watercourse, on_delete=models.DO_NOTHING, related_name='yearly_consumption_set')
    date = models.DateField()
    consumption = models.DecimalField(max_digits=18, decimal_places=6)
    p_quarter1 = models.DecimalField(max_digits=18, decimal_places=6, default=0, blank=True)
    p_quarter2 = models.DecimalField(max_digits=18, decimal_places=6, default=0, blank=True)
    p_quarter3 = models.DecimalField(max_digits=18, decimal_places=6, default=0, blank=True)
    p_quarter4 = models.DecimalField(max_digits=18, decimal_places=6, default=0, blank=True)
