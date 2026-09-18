from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

OPENS_AT = time(8, 0)
CLOSES_AT = time(22, 0)
PEAK_STARTS_AT = time(18, 0)
PEAK_ENDS_AT = time(22, 0)
PEAK_MULTIPLIER = Decimal("1.5")


class Sport(models.TextChoices):
    VOLLEYBALL = "VOLLEYBALL"
    BASKETBALL = "BASKETBALL"
    SOCCER = "SOCCER"


class Tier(models.TextChoices):
    BASIC = "BASIC"
    PREMIUM = "PREMIUM"
    DELUXE = "DELUXE"


class BookingStatus(models.TextChoices):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class Role(models.TextChoices):
    STAFF = "STAFF"
    CUSTOMER = "CUSTOMER"


class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=Role.values),
                name="user_role_valid",
            ),
        ]


class Court(models.Model):
    name = models.CharField(max_length=100, unique=True)
    sport = models.CharField(max_length=20, choices=Sport)
    tier = models.CharField(max_length=20, choices=Tier)
    hour_price = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(hour_price__gt=0), name="court_hour_price_positive"
            ),
            models.CheckConstraint(
                condition=Q(sport__in=Sport.values), name="court_sport_valid"
            ),
            models.CheckConstraint(
                condition=Q(tier__in=Tier.values), name="court_tier_valid"
            ),
        ]


class Booking(models.Model):
    court = models.ForeignKey(Court, on_delete=models.PROTECT, related_name="bookings")
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="bookings"
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_bookings"
    )
    status = models.CharField(
        max_length=20, choices=BookingStatus, default=BookingStatus.ACTIVE
    )

    def __str__(self):
        user = self.user.username if self.user else "-"
        return f"{user} - {self.court.name} ({self.starts_at} to {self.ends_at}, created by {self.created_by.username})"

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(starts_at__lt=models.F("ends_at")),
                name="booking_starts_before_ends",
            ),
            models.CheckConstraint(
                condition=Q(status__in=BookingStatus.values),
                name="booking_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    starts_at=models.Func(
                        models.F("starts_at"),
                        function="DATE_TRUNC",
                        template="DATE_TRUNC('hour', %(expressions)s)",
                        output_field=models.DateTimeField(),
                    )
                ),
                name="booking_starts_at_full_hour",
            ),
            models.CheckConstraint(
                condition=Q(ends_at=models.F("starts_at") + timedelta(hours=1)),
                name="booking_slot_lasts_one_hour",
            ),
            models.UniqueConstraint(
                fields=["court", "starts_at"],
                name="unique_booking_per_court_time",
                condition=Q(status=BookingStatus.ACTIVE),
            ),
        ]
