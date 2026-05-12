from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed a local development database with a login user, sources, jobs, and contacts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default=settings.SEED_DEMO_ADMIN_EMAIL,
            help="Email for the dev superuser",
        )
        parser.add_argument(
            "--password",
            default=settings.SEED_DEMO_ADMIN_PASSWORD,
            help="Password for the dev superuser",
        )
        parser.add_argument(
            "--skip-user",
            action="store_true",
            help="Skip creating the dev superuser",
        )

    def handle(self, *args, **options):
        call_command("seed_websites")

        if not options["skip_user"]:
            self._seed_user(options["email"], options["password"])

    def _seed_user(self, email, password):
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            email=email,
            defaults={
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        status = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Dev superuser {email} {status}."))
