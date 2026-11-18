from django import forms


class StateSelect(forms.Select):
    """Expose a stable state slug on each state option for dependent selects."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        state = getattr(value, "instance", None) if value else None
        if state is not None:
            option["attrs"]["data-state-slug"] = state.slug
        return option


class CitySelect(forms.Select):
    """Expose the related state's slug on each city option."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        city = getattr(value, "instance", None) if value else None
        if city is not None:
            option["attrs"]["data-state-slug"] = city.state.slug
        return option
