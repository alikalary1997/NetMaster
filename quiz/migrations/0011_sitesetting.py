from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0010_userprofile_is_blocked"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("study_live", models.BooleanField(default=False)),
            ],
        ),
    ]
