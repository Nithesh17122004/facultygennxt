from django import forms


class CitySelect(forms.Select):
    """Select widget that exposes each city's state for dependent filtering."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        if value and getattr(value, "instance", None) is not None:
            option["attrs"]["data-state"] = str(value.instance.state_id)
        return option


class StateSelect(forms.Select):
    pass
