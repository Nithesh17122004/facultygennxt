from django import forms


class CitySelect(forms.Select):
    """Select widget that exposes each city's state ID for dependent filtering."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        city = getattr(value, "instance", None) if value else None
        if city is not None:
            # StateSelect is a ModelChoiceField whose HTML value is the state's PK.
            option["attrs"]["data-state"] = str(city.state_id)
        return option


class StateSelect(forms.Select):
    pass
