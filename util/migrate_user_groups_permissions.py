import django
from django.db import connection

django.setup()

from django.contrib.auth.models import Group, User, Permission

with connection.cursor() as cursor:
    cursor.execute("SELECT name FROM auth_groups ORDER BY id")
    rows = cursor.fetchall()
    for row in rows:
        Group.objects.create(name=row[0])

with connection.cursor() as cursor:
    cursor.execute("SELECT auth_permissions.codename, auth_groups.name FROM auth_groups_permissions inner join auth_groups on auth_groups_permissions.group_id=auth_groups.id inner join auth_permissions on auth_groups_permissions.permission_id=auth_permissions.id")
    rows = cursor.fetchall()
    for permission_codename, group_name in rows:
        permission = Permission.objects.get(codename=permission_codename)
        group = Group.objects.get(name=group_name)
        group.permissions.add(permission)

with connection.cursor() as cursor:
    cursor.execute("SELECT auth_permissions.codename, auth_users.username FROM auth_users_user_permissions inner join auth_users on auth_users_user_permissions.user_id=auth_users.id inner join auth_permissions on auth_users_user_permissions.permission_id=auth_permissions.id")
    rows = cursor.fetchall()
    for permission_codename, username in rows:
        if '_site' not in permission_codename:
            permission = Permission.objects.get(codename=permission_codename)
            user = User.objects.get(username=username)
            user.user_permissions.add(permission)
