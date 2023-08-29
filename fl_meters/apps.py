from django.apps import AppConfig
from django.core.checks import Error, register

class FlMetersConfig(AppConfig):
    name = 'fl_meters'
    verbose_name = "Flowless Meters"

    def ready(self):
        import fl_meters.signals

        @register()
        def template_files_exist_check(app_configs, **kwargs):
            errors = []
            try:
                from fl_meters import custom_signal_handlers
            except ImportError as e:
                errors.append(
                    Error(
                        "| The file `custom_signal_handlers.py` file does not exist.",
                        hint="""Create a `custom_signal_handlers.py` file based on the 
                        `custom_signal_handlers.template.py` template file.""",
                        obj=e,
                        id='fl_meters.C001',
                    )
                )
            return errors
