import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from crm.models import CarModel, Client, Deal, DealStatusHistory, Interaction, LeadSource, Task

PASSWORD = "Demo12345!"

USERS = [
    ('admin', 'Айгерим', 'Садыкова', Profile.Role.ADMIN),
    ("head", "Ерлан", "Касымов", Profile.Role.HEAD),
    ("manager1", "Дана", "Ахметова", Profile.Role.MANAGER),
    ("manager2", "Тимур", "Нурланов", Profile.Role.MANAGER),
    ("manager3", "Алия", "Жумабаева", Profile.Role.MANAGER),
    ("manager4", "Санжар", "Абенов", Profile.Role.MANAGER),
    ("manager5", "Айдана", "Серикова", Profile.Role.MANAGER),
]

CARS = [
    ("Kia", "Rio", "sedan", 9_490_000),
    ("Kia", "Cerato", "sedan", 11_990_000),
    ("Kia", "K5", "sedan", 15_490_000),
    ("Kia", "Soul", "hatchback", 10_990_000),
    ("Kia", "Seltos", "crossover", 12_490_000),
    ("Kia", "Sportage", "crossover", 15_990_000),
    ("Kia", "Sorento", "suv", 20_990_000),
    ("Kia", "Mohave", "suv", 29_990_000),
    ("Kia", "Carnival", "minivan", 25_990_000),
]

SOURCES = [
    ("Paid Search", "online"),
    ("Paid Socials", "online"),
    ("Instagram/Facebook", "online"),
    ("Сайт", "online"),
    ("Реферальные ссылки", "online"),
]


FINAL_PLAN = {"new": 2, "in_progress": 3, "test_drive": 2, "negotiation": 2, "won": 4, "lost": 2}

FIRST_M = ["Нурлан", "Арман", "Ерболат", "Данияр", "Санжар", "Руслан", "Бауыржан", "Олжас", "Максат"]
FIRST_F = ["Асель", "Мадина", "Жанна", "Айдана", "Камила", "Алина", "Гульнара", "Зарина", "Динара"]
LAST = ["Абдрахманов", "Беков", "Сейткали", "Омаров", "Искаков", "Тулегенов", "Мукашев",
        "Жаксылыков", "Ким", "Петров", "Сулейменов", "Каримов", "Есенов", "Байжанов"]
CITIES = ["Алматы", "Астана", "Шымкент", "Караганда", "Актобе"]
LOST_REASONS = ["Дорого", "Купил у конкурента", "Не устроили условия кредита",
                "Нет нужной комплектации", "Перестал выходить на связь"]
TASK_TITLES = ["Перезвонить клиенту", "Отправить коммерческое предложение", "Согласовать тест-драйв",
               "Уточнить условия трейд-ина", "Подготовить расчёт кредита"]


PATHS = {
    "new": ["new"],
    "in_progress": ["new", "in_progress"],
    "test_drive": ["new", "in_progress", "test_drive"],
    "negotiation": ["new", "in_progress", "test_drive", "negotiation"],
    "won": ["new", "in_progress", "test_drive", "negotiation", "won"],
    "lost": ["new", "in_progress", "lost"],
}


def random_name(rnd):
    last = rnd.choice(LAST)
    if rnd.random() < .5:
        return f"{rnd.choice(FIRST_M)} {last}"
    if last.endswith(("ов", "ев", "ин")):
        last += "а"  # Беков → Бекова
    return f"{rnd.choice(FIRST_F)} {last}"


class Command(BaseCommand):
    help = "Создаёт демо-пользователей, справочники, клиентов, сделки и задачи"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Удалить существующие сделки и клиентов")

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(42)

        if opts["reset"]:
            Task.objects.all().delete()
            Deal.objects.all().delete()
            Client.objects.all().delete()


        users = {}
        for username, first, last, role in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": f"{username}@kia-center.kz"},
            )
            if created:
                user.set_password(PASSWORD)
                user.is_staff = role == Profile.Role.ADMIN
                user.is_superuser = role == Profile.Role.ADMIN
                user.save()
            user.profile.role = role
            user.profile.save()
            users[username] = user
        managers = [u for u in users.values() if u.profile.role == Profile.Role.MANAGER]


        cars = [CarModel.objects.get_or_create(brand=b, name=n, defaults={"body_type": t, "base_price": p})[0]
                for b, n, t, p in CARS]
        sources = [LeadSource.objects.get_or_create(name=n, defaults={"channel": c})[0] for n, c in SOURCES]

        if Deal.objects.exists():
            self.stdout.write(self.style.WARNING("Сделки уже есть - пропускаю. Запустите с --reset."))
            return


        finals = [status for status, count in FINAL_PLAN.items() for _ in range(count)]
        rnd.shuffle(finals)

        now = timezone.now()
        for i, final in enumerate(finals):
            client = Client.objects.create(
                full_name=random_name(rnd),
                phone=f"+770{rnd.randint(10_000_000, 99_999_999)}",
                email=f"client{i + 1}@mail.kz" if rnd.random() < .6 else "",
                city=rnd.choice(CITIES),
            )
            car = rnd.choice(cars)
            manager = managers[i % len(managers)]   # у каждого по 3 сделки
            source = sources[(i // 3) % len(sources)]
            path = PATHS[final]
            created = now - timedelta(days=rnd.randint(len(path) * 4, 60), hours=rnd.randint(0, 10))

            deal = Deal.objects.create(client=client, car_model=car, source=source, manager=manager, status=final)
            if final == "won":
                deal.amount = car.base_price + Decimal(rnd.randrange(0, 2_000_000, 50_000))
            if final == "lost":
                deal.lost_reason = rnd.choice(LOST_REASONS)

            # история статусов: сделка проходит путь по воронке, интервал в несколько дней
            step_time = created
            prev = ""
            for status in path:
                h = DealStatusHistory.objects.create(deal=deal, from_status=prev, to_status=status, changed_by=manager)
                DealStatusHistory.objects.filter(pk=h.pk).update(changed_at=min(step_time, now))
                prev = status
                step_time += timedelta(days=rnd.randint(1, 4))
            if final in ("won", "lost"):
                deal.closed_at = min(step_time, now)
            deal.save()

            Deal.objects.filter(pk=deal.pk).update(created_at=created)


            for _ in range(rnd.randint(1, 3)):
                it = Interaction.objects.create(
                    deal=deal, kind=rnd.choice(["call", "call", "message", "meeting"]), author=manager,
                    comment="Обсудили комплектации и условия покупки.",
                )
                Interaction.objects.filter(pk=it.pk).update(
                    created_at=min(created + timedelta(hours=rnd.randint(1, 48)), now))

            # задачи только по открытым сделкам; часть из них специально просрочена
            if final not in ("won", "lost"):
                Task.objects.create(
                    title=rnd.choice(TASK_TITLES), deal=deal, assignee=manager, created_by=manager,
                    due_date=now + timedelta(days=rnd.randint(-3, 5), hours=rnd.randint(0, 8)),
                )

        self.stdout.write(self.style.SUCCESS(
            f"Готово: {Deal.objects.count()} сделок, {Client.objects.count()} клиентов, "
            f"{Task.objects.count()} задач. Пароль демо-пользователей: {PASSWORD}"
        ))