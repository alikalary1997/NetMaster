# Generated migration for drag-and-drop matching questions

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quiz", "0004_alter_answer_text"),
    ]

    operations = [
        # 1. Add question_type field to Question (default='mc' keeps existing questions working)
        migrations.AddField(
            model_name="question",
            name="question_type",
            field=models.CharField(
                choices=[
                    ("mc", "Multiple Choice"),
                    ("matching", "Drag & Drop Matching"),
                ],
                default="mc",
                max_length=10,
            ),
        ),
        # 2. Create MatchingPair model
        migrations.CreateModel(
            name="MatchingPair",
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
                ("left_text", models.CharField(max_length=500)),
                ("right_text", models.CharField(max_length=500)),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="matching_pairs",
                        to="quiz.question",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        # 3. Add matching_answer JSONField to UserAnswer
        migrations.AddField(
            model_name="useranswer",
            name="matching_answer",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
