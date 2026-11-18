from django import forms


class CitySelect(forms.Select):
    """Select widget that exposes each city's state slug for dependent filtering."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        city = getattr(value, "instance", None) if value else None
        if city is not None:
            option["attrs"]["data-state"] = city.state.slug
        return option


class StateSelect(forms.Select):
    pass
