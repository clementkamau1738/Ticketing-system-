from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from events.models import Event
from tickets.models import IssuedTicket
from orders.models import Order

class Command(BaseCommand):
    help = 'Setup default RBAC groups and permissions'

    def handle(self, *args, **kwargs):
        # 1. Define Groups and their specific permissions
        roles = {
            'Organizer': [
                # Event Permissions
                'add_event', 'change_event', 'delete_event', 'view_event',
                'can_create_event', 'can_edit_own_event',
                # Ticket Permissions
                'view_ticket', 'change_ticket',
                # IssuedTicket Permissions
                'can_scan_tickets',
            ],
            'Admin': [
                # Inherits everything (conceptually, or we explicitly add)
                # Events
                'add_event', 'change_event', 'delete_event', 'view_event',
                'can_create_event', 'can_edit_own_event',
                # Tickets
                'add_ticket', 'change_ticket', 'delete_ticket', 'view_ticket',
                # IssuedTickets
                'can_scan_tickets',
                # Orders
                'view_order', 'change_order',
                'can_issue_refunds',
            ],
            'Attendee': [
                # Mostly read-only, handled by public views, but maybe:
                'view_event',
            ]
        }

        for role_name, perms in roles.items():
            group, created = Group.objects.get_or_create(name=role_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {role_name}'))
            else:
                self.stdout.write(f'Updating group: {role_name}')

            # Clear existing permissions to ensure clean slate or just add?
            # Let's just add missing ones.
            
            for codename in perms:
                try:
                    permission = Permission.objects.get(codename=codename)
                    group.permissions.add(permission)
                    self.stdout.write(f'  + Added {codename} to {role_name}')
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'  ! Permission {codename} not found'))

            self.stdout.write(self.style.SUCCESS(f'Successfully updated {role_name} permissions'))

        self.stdout.write(self.style.SUCCESS('RBAC setup completed.'))
