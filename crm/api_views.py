from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsHeadOrAdmin
from accounts.roles import is_admin, is_head_or_admin

from . import services
from .filters import DealFilter, TaskFilter
from .models import CarModel, Client, Interaction, LeadSource
from .permissions import DealPermission, ReadOnlyOrHeadAdmin
from .serializers import (
    AssignManagerSerializer, CarModelSerializer, ChangeStatusSerializer, ClientSerializer,
    DealCreateSerializer, DealSerializer, DealStatusHistorySerializer, InteractionSerializer,
    LeadSourceSerializer, TaskSerializer,
)


def business_error_response(exc):
    return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class CarModelViewSet(viewsets.ModelViewSet):
    queryset = CarModel.objects.all()
    serializer_class = CarModelSerializer
    permission_classes = [ReadOnlyOrHeadAdmin]
    filterset_fields = ['brand', 'body_type', 'is_active']
    search_fields = ['brand', 'name']
    ordering_fields = ['brand', 'name', 'base_price']


class LeadSourceViewSet(viewsets.ModelViewSet):
    queryset = LeadSource.objects.all()
    serializer_class = LeadSourceSerializer
    permission_classes = [ReadOnlyOrHeadAdmin]
    filterset_fields = ['channel', 'is_active']
    search_fields = ['name']


class ClientViewSet(viewsets.ModelViewSet):
    """Менеджер видит клиентов по своим сделкам и тех, кого добавил сам."""

    serializer_class = ClientSerializer
    filterset_fields = ['city']
    search_fields = ['full_name', 'phone', 'email']
    ordering_fields = ['full_name', 'created_at']

    def get_queryset(self):
        qs = Client.objects.annotate(deals_count=Count('deals', distinct=True))
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if is_head_or_admin(user):
            return qs
        return qs.filter(Q(deals__manager=user) | Q(created_by=user)).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        if not is_admin(request.user):
            return Response({'detail': 'Удалять клиентов может только администратор.'},
                            status=status.HTTP_403_FORBIDDEN)
        client = self.get_object()
        if client.deals.exists():
            return Response({'detail': 'У клиента есть сделки - удалить его нельзя.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)


class DealViewSet(viewsets.ModelViewSet):
    """Статус сделок меняется только через /change_status/, чтобы соблюдались правила воронки."""

    permission_classes = [DealPermission]
    filterset_class = DealFilter
    search_fields = ['client__full_name', 'client__phone', 'car_model__name', 'car_model__brand']
    ordering_fields = ['created_at', 'amount', 'updated_at']

    def get_queryset(self):
        return services.deals_for(self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return DealCreateSerializer
        return DealSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deal = services.create_deal(user=request.user, **serializer.validated_data)
        return Response(DealSerializer(deal).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ChangeStatusSerializer, responses=DealSerializer,
                   summary='Сменить статус сделки по правилам воронки')
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        deal = self.get_object()
        ser = ChangeStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            deal = services.change_deal_status(deal, ser.validated_data['status'], user=request.user,
                                               comment=ser.validated_data.get('comment', ''),
                                               amount=ser.validated_data.get('amount'),
                                               lost_reason=ser.validated_data.get('lost_reason', ''))
        except services.BusinessError as exc:
            return business_error_response(exc)
        return Response(DealSerializer(deal).data)

    @extend_schema(request=AssignManagerSerializer, responses=DealSerializer,
                   summary='Назначить ответственного менеджера (руководитель/админ)')
    @action(detail=True, methods=['post'], permission_classes=[IsHeadOrAdmin])
    def assign(self, request, pk=None):
        deal = self.get_object()
        ser = AssignManagerSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            deal = services.assign_manager(deal, ser.validated_data['manager'], user=request.user)
        except services.BusinessError as exc:
            return business_error_response(exc)
        return Response(DealSerializer(deal).data)

    @extend_schema(responses=DealStatusHistorySerializer(many=True), summary='История статусов сделки')
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        deal = self.get_object()
        return Response(DealStatusHistorySerializer(deal.history.select_related('changed_by'), many=True).data)


class InteractionViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                         mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Касания с клиентом. Изменять и удалять их нельзя - это журнал контакта с лидами/клиентами."""

    serializer_class = InteractionSerializer
    filterset_fields = ['deal', 'kind']
    ordering_fields = ['created_at']

    def get_queryset(self):
        deals = services.deals_for(self.request.user)
        return Interaction.objects.filter(deal__in=deals).select_related('author')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    filterset_class = TaskFilter
    search_fields = ['title', 'description']
    ordering_fields = ['due_date', 'created_at']

    def get_queryset(self):
        return services.tasks_for(self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        assignee = serializer.validated_data.get('assignee')
        # менеджер ставит задачи только себе, руководитель - кому угодно
        if not is_head_or_admin(user) or assignee is None:
            assignee = user
        serializer.save(assignee=assignee, created_by=user)

    @extend_schema(summary='Мои задачи на сегодня')
    @action(detail=False, methods=['get'])
    def today(self, request):
        today = timezone.localdate()
        qs = self.get_queryset().filter(assignee=request.user, is_done=False, due_date__date=today)
        return Response(TaskSerializer(qs, many=True).data)

    @extend_schema(summary='Просроченные задачи')
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        qs = self.get_queryset().filter(is_done=False, due_date__lt=timezone.now())
        return Response(TaskSerializer(qs, many=True).data)

    @extend_schema(request=None, summary='Отметить задачу выполненной')
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        try:
            task = services.complete_task(task, user=request.user)
        except services.BusinessError as exc:
            return business_error_response(exc)
        return Response(TaskSerializer(task).data)


class AnalyticsView(APIView):
    """Сводная аналитика воронки. Менеджер получает статистику по своим сделкам,
    руководитель и админ - по всему дилерскому центру."""

    @extend_schema(
        parameters=[
            OpenApiParameter('date_from', str, description='Сделки, созданные с даты (YYYY-MM-DD)'),
            OpenApiParameter('date_to', str, description='Сделки, созданные по дату (YYYY-MM-DD)'),
        ],
        responses=OpenApiTypes.OBJECT,
        summary='Аналитика: воронка, конверсия по источникам, менеджерам и моделям',
    )
    def get(self, request):
        qs = services.deals_for(request.user)
        f = DealFilter(
            {'created_from': request.query_params.get('date_from'),
             'created_to': request.query_params.get('date_to')},
            queryset=qs,
        )
        if not f.is_valid():
            return Response(f.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(services.analytics_summary(f.qs))