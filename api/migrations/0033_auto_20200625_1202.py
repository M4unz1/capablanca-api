# Generated by Django 3.0.7 on 2020-06-25 10:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0032_board_board_fen"),
    ]

    operations = [
        migrations.AlterField(
            model_name="board",
            name="board_fen",
            field=models.TextField(
                default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
            ),
        ),
    ]
