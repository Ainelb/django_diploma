from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

phone_validator = RegexValidator(
    regex=r'^\+7\d{10}$',
    message='Телефон в формате +7XXXXXXXXXX (11 цифр после плюса).',
)


class CarModel(models.Model):
    """Модель автомобиля, которую продаёт дилерский центр."""

    class BodyType(models.TextChoices):
        SEDAN = 'sedan', 'Седан'
        CROSSOVER = 'crossover', 'Кроссовер'
        SUV = 'suv', 'Внедорожник'
        HATCHBACK = 'hatchback', 'Хэтчбек'
        MINIVAN = 'minivan', 'Минивэн'

    brand = models.CharField('Марка', max_length=50)
    name = models.CharField('Модель', max_length=50)
    body_type = models.CharField('Кузов', max_length=20, choices=BodyType.choices)
    base_price = models.DecimalField(
        'Цена от, ₸', max_digits=12, decimal_places=0, validators=[MinValueValidator(1)]
    )
    is_active = models.BooleanField('В продаже', default=True)

    class Meta:
        verbose_name = 'Модель авто'
        verbose_name_plural = 'Модели авто'
        ordering = ['brand', 'name']
        constraints = [
            models.UniqueConstraint(fields=['brand', 'name'], name='unique_brand_model'),
        ]

    def __str__(self):
        return f'{self.brand} {self.name}'


class LeadSource(models.Model):
    """Источник лида: сайт, Instagram, звонок, визит в салон и т.д."""

    class Channel(models.TextChoices):
        ONLINE = 'online', 'Онлайн'
        OFFLINE = 'offline', 'Офлайн'

    name = models.CharField('Название', max_length=50, unique=True)
    channel = models.CharField('Канал', max_length=10, choices=Channel.choices)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Источник лида'
        verbose_name_plural = 'Источники лидов'
        ordering = ['name']

    def __str__(self):
        return self.name


class Client(models.Model):
    full_name = models.CharField('ФИО', max_length=150)
    phone = models.CharField('Телефон', max_length=12, unique=True, validators=[phone_validator])
    email = models.EmailField('Email', blank=True)
    city = models.CharField('Город', max_length=50, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_clients', verbose_name='Кто добавил',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} ({self.phone})'


class Deal(models.Model):
    """Сделка - путь одного клиента по воронке продаж к покупке конкретной модели."""

    class Status(models.TextChoices):
        NEW = 'new', 'Новый лид'
        IN_PROGRESS = 'in_progress', 'В работе'
        TEST_DRIVE = 'test_drive', 'Тест-драйв'
        NEGOTIATION = 'negotiation', 'Переговоры'
        WON = 'won', 'Продан'
        LOST = 'lost', 'Отказ'

    # Разрешённые переходы между статусами - главная бизнес-логика воронки.
    # Например, нельзя перевести только что пришедший лид сразу в «Продан».
    TRANSITIONS = {
        Status.NEW: [Status.IN_PROGRESS, Status.LOST],
        Status.IN_PROGRESS: [Status.TEST_DRIVE, Status.NEGOTIATION, Status.LOST],
        Status.TEST_DRIVE: [Status.NEGOTIATION, Status.LOST],
        Status.NEGOTIATION: [Status.WON, Status.LOST],
        Status.WON: [],
        Status.LOST: [Status.IN_PROGRESS],  # клиент вернулся - сделку можно возобновить
    }
    CLOSED_STATUSES = (Status.WON, Status.LOST)

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='deals', verbose_name='Клиент')
    car_model = models.ForeignKey(CarModel, on_delete=models.PROTECT, related_name='deals', verbose_name='Модель авто')
    source = models.ForeignKey(LeadSource, on_delete=models.PROTECT, related_name='deals', verbose_name='Источник')
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deals', verbose_name='Менеджер',
    )
    status = models.CharField('Статус', max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    amount = models.DecimalField(
        'Сумма сделки, ₸', max_digits=12, decimal_places=0, null=True, blank=True,
        validators=[MinValueValidator(1)],
    )
    lost_reason = models.CharField('Причина отказа', max_length=255, blank=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)
    closed_at = models.DateTimeField('Закрыта', null=True, blank=True)

    class Meta:
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'
        ordering = ['-created_at']

    def __str__(self):
        return f'#{self.pk} {self.client.full_name} - {self.car_model}'

    @property
    def allowed_statuses(self):
        return self.TRANSITIONS.get(self.status, [])

    def can_transition_to(self, new_status):
        return new_status in self.allowed_statuses

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES


class DealStatusHistory(models.Model):
    """Журнал смены статусов: кто, когда и откуда куда перевёл сделку."""

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='history', verbose_name='Сделка')
    from_status = models.CharField('Был статус', max_length=20, choices=Deal.Status.choices, blank=True)
    to_status = models.CharField('Стал статус', max_length=20, choices=Deal.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='Кто изменил'
    )
    comment = models.CharField('Комментарий', max_length=255, blank=True)
    changed_at = models.DateTimeField('Когда', auto_now_add=True)

    class Meta:
        verbose_name = 'Изменение статуса'
        verbose_name_plural = 'История статусов'
        ordering = ['changed_at']

    def __str__(self):
        return f'{self.deal_id}: {self.from_status or "-"} → {self.to_status}'


class Interaction(models.Model):
    """Касание с клиентом: звонок, встреча, тест-драйв, сообщение, заметка."""

    class Kind(models.TextChoices):
        CALL = 'call', 'Звонок'
        MEETING = 'meeting', 'Встреча в салоне'
        TEST_DRIVE = 'test_drive', 'Тест-драйв'
        MESSAGE = 'message', 'Сообщение'
        NOTE = 'note', 'Заметка'

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='interactions', verbose_name='Сделка')
    kind = models.CharField('Тип', max_length=20, choices=Kind.choices)
    comment = models.TextField('Комментарий')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='Автор'
    )
    created_at = models.DateTimeField('Когда', auto_now_add=True)

    class Meta:
        verbose_name = 'Касание'
        verbose_name_plural = 'История касаний'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_kind_display()} по сделке #{self.deal_id}'


class Task(models.Model):
    """Задача менеджера, например «перезвонить клиенту завтра в 11:00»."""

    title = models.CharField('Задача', max_length=200)
    description = models.TextField('Описание', blank=True)
    deal = models.ForeignKey(
        Deal, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks', verbose_name='Сделка'
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tasks', verbose_name='Исполнитель'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='created_tasks', verbose_name='Кто поставил',
    )
    due_date = models.DateTimeField('Срок', db_index=True)
    is_done = models.BooleanField('Выполнена', default=False)
    done_at = models.DateTimeField('Когда выполнена', null=True, blank=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['is_done', 'due_date']

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return not self.is_done and self.due_date < timezone.now()