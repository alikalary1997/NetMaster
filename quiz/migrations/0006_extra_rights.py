import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quiz", "0005_add_matching_questions"),
    ]

    operations = [
        migrations.CreateModel(
            name="MatchingRight",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.CharField(max_length=500)),
                (
                    "pair",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="extra_rights",
                        to="quiz.matchingpair",
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
    ]
