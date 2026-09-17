from functools import cached_property
from pathlib import Path

import django.forms
from django.forms.renderers import DjangoTemplates


class InventarioFormRenderer(DjangoTemplates):
    @cached_property
    def engine(self):
        return self.backend(
            {
                "APP_DIRS": True,
                "DIRS": [
                    Path(__file__).resolve().parent.parent / "templates",
                    Path(django.forms.__file__).parent / "templates",
                ],
                "NAME": "djangoforms",
                "OPTIONS": {},
            }
        )