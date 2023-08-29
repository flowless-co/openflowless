from django.forms import ModelForm, ModelMultipleChoiceField, ValidationError
from django.forms.widgets import TextInput

from .models import Zone, Meter


class ZoneAdminForm(ModelForm):
    inputs = ModelMultipleChoiceField(queryset=Meter.objects.all(), required=False)
    outputs = ModelMultipleChoiceField(queryset=Meter.objects.all(), required=False)

    class Meta:
        model = Zone
        fields = '__all__'
        widgets = {
            'color': TextInput(attrs={'type': 'color'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields['inputs'].initial = self.instance.input_meters.all()
            self.fields['outputs'].initial = self.instance.output_meters.all()

    def clean_inputs(self):
        inputs = self.cleaned_data.get('inputs')
        for meter in inputs:
            if meter.input_for_id is not None:
                raise ValidationError("A meter is already set as input for another zone", code='conflict')
        return inputs

    def clean_outputs(self):
        outputs = self.cleaned_data.get('outputs')
        for meter in outputs:
            if meter.output_for_id is not None:
                raise ValidationError("A meter is already set as output for another zone")
        return outputs

    def clean(self):
        cleaned_data = super().clean()
        inputs = cleaned_data.get('inputs')
        outputs = cleaned_data.get('outputs')

        if inputs is not None and outputs is not None:
            if len(inputs.intersection(outputs)) > 0:
                raise ValidationError("Same meter can't exist as input and output at the same time")

        return cleaned_data

    def save(self, *args, **kwargs):
        instance = super().save(commit=False)

        for meter in self.cleaned_data['inputs']:
            meter.input_for = instance
        for meter in self.cleaned_data['outputs']:
            meter.output_for = instance

        instance.save()

        # save_m2m() is not working for some reason
        # self.save_m2m()

        # workaround:
        for meter in self.cleaned_data['inputs']:
            meter.save()
        for meter in self.cleaned_data['outputs']:
            meter.save()


        return instance
