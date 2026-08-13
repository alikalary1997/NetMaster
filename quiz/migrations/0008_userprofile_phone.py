from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0007_userprofile_has_full_access"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=15),
        ),
    ]
