from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("language", "0003_alter_course_options"),
    ]

    operations = [
        migrations.RenameField(
            model_name="item",
            old_name="source_language_script",
            new_name="text",
        ),
        migrations.RenameField(
            model_name="item",
            old_name="target_language_transliteration",
            new_name="transliteration",
        ),
    ]
