from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0006_extra_rights"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="has_full_access",
            field=models.BooleanField(default=False),
        ),
    ]
