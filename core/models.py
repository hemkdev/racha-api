from datetime import time
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


class User(AbstractUser):
    pass


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
