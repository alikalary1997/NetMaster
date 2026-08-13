from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0008_userprofile_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="premium_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
