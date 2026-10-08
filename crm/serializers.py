from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from .models import CarModel, Client, Deal, DealStatusHistory, Interaction, LeadSource, Task


class CarModelSerializer(serializers.ModelSerializer):
    body_type_display = serializers.CharField(source='get_body_type_display', read_only=True)

    class Meta:
        model = CarModel
        fields = ('id', 'brand', 'name', 'body_type', 'body_type_display', 'base_price', 'is_active')


class LeadSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadSource
        fields = ('id', 'name', 'channel', 'is_active')


class ClientSerializer(serializers.ModelSerializer):
    deals_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Client
        fields = ('id', 'full_name', 'phone', 'email', 'city', 'created_at', 'deals_count')
        read_only_fields = ('created_at',)

    def validate_full_name(self, value):
        value = ' '.join(value.split())
        if len(value) < 3:
            raise serializers.ValidationError('Укажите имя клиента полностью.')
        return value


class UserShortSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'full_name')

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username


class DealSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    client_name = serializers.CharField(source='client.full_name', read_only=True)
    car_model_name = serializers.CharField(source='car_model.__str__', read_only=True)
    source_name = serializers.CharField(source='source.name', read_only=True)
    manager_info = UserShortSerializer(source='manager', read_only=True)
    allowed_statuses = serializers.ListField(read_only=True)

    class Meta:
        model = Deal
        fields = (
            'id', 'client', 'client_name', 'car_model', 'car_model_name', 'source', 'source_name',
            'manager', 'manager_info', 'status', 'status_display', 'allowed_statuses',
            'amount', 'lost_reason', 'created_at', 'updated_at', 'closed_at',
        )
        # статус меняется только через отдельный endpoint change_status,
        # менеджер - через assign; так соблюдаются правила воронки
        read_only_fields = ('status', 'lost_reason', 'created_at', 'updated_at', 'closed_at', 'manager')

    def validate_car_model(self, value):
        if not value.is_active:
            raise serializers.ValidationError('Эта модель снята с продажи.')
        return value

    def validate_source(self, value):
        if not value.is_active:
            raise serializers.ValidationError('Этот источник лидов отключён.')
        return value


class DealCreateSerializer(DealSerializer):
    """При создании руководитель может сразу указать менеджера."""

    class Meta(DealSerializer.Meta):
        read_only_fields = ('status', 'lost_reason', 'created_at', 'updated_at', 'closed_at')


class ChangeStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Deal.Status.choices)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=255)
    amount = serializers.DecimalField(max_digits=12, decimal_places=0, required=False, min_value=1)
    lost_reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class AssignManagerSerializer(serializers.Serializer):
    manager = serializers.PrimaryKeyRelatedField(queryset=User.objects.select_related('profile'))


class DealStatusHistorySerializer(serializers.ModelSerializer):
    from_status_display = serializers.CharField(source='get_from_status_display', read_only=True)
    to_status_display = serializers.CharField(source='get_to_status_display', read_only=True)
    changed_by = UserShortSerializer(read_only=True)

    class Meta:
        model = DealStatusHistory
        fields = ('id', 'from_status', 'from_status_display', 'to_status', 'to_status_display',
                  'changed_by', 'comment', 'changed_at')


class InteractionSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    author = UserShortSerializer(read_only=True)

    class Meta:
        model = Interaction
        fields = ('id', 'deal', 'kind', 'kind_display', 'comment', 'author', 'created_at')
        read_only_fields = ('created_at',)

    def validate_deal(self, deal):
        from .services import deals_for
        if not deals_for(self.context['request'].user).filter(pk=deal.pk).exists():
            raise serializers.ValidationError('Сделка не найдена или недоступна.')
        return deal


class TaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)
    assignee_info = UserShortSerializer(source='assignee', read_only=True)
    deal_title = serializers.CharField(source='deal.__str__', read_only=True, default=None)

    class Meta:
        model = Task
        fields = ('id', 'title', 'description', 'deal', 'deal_title', 'assignee', 'assignee_info',
                  'due_date', 'is_done', 'is_overdue', 'done_at', 'created_at')
        read_only_fields = ('is_done', 'done_at', 'created_at')
        extra_kwargs = {'assignee': {'required': False}}

    def validate_due_date(self, value):
        if self.instance is None and value < timezone.now():
            raise serializers.ValidationError('Срок задачи не может быть в прошлом.')
        return value

    def validate_deal(self, deal):
        from .services import deals_for
        if deal and not deals_for(self.context['request'].user).filter(pk=deal.pk).exists():
            raise serializers.ValidationError('Сделка не найдена или недоступна.')
        return deal