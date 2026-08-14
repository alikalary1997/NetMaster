from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0009_userprofile_premium_expires_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="is_blocked",
            field=models.BooleanField(default=False),
        ),
    ]
