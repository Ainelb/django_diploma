import django_filters

from .models import Deal, Task


class DealFilter(django_filters.FilterSet):
    created_from = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte', label='Создана с')
    created_to = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte', label='Создана по')
    amount_min = django_filters.NumberFilter(field_name='amount', lookup_expr='gte', label='Сумма от')
    amount_max = django_filters.NumberFilter(field_name='amount', lookup_expr='lte', label='Сумма до')
    status = django_filters.MultipleChoiceFilter(choices=Deal.Status.choices)
    brand = django_filters.CharFilter(field_name='car_model__brand', lookup_expr='iexact', label='Марка')

    class Meta:
        model = Deal
        fields = ['status', 'source', 'car_model', 'manager', 'brand']


class TaskFilter(django_filters.FilterSet):
    due_from = django_filters.DateFilter(field_name='due_date', lookup_expr='date__gte')
    due_to = django_filters.DateFilter(field_name='due_date', lookup_expr='date__lte')

    class Meta:
        model = Task
        fields = ['is_done', 'assignee', 'deal']