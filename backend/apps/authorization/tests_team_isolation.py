import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from apps.authorization.models import Role, Permission, RolePermission, UserRole, UserPermissionGrant, ScopeChoices
from apps.organization.models import Organization, Branch, Department, Team
from unittest.mock import patch
from apps.employees.models import Employee

User = get_user_model()

@pytest.fixture(autouse=True)
def mock_network_access():
    with patch('apps.authorization.permissions.NetworkAccessService.is_remote_access_allowed', return_value=True):
        yield

@pytest.fixture
def setup_test_data():
    org1 = Organization.objects.create(name="Org 1")
    org2 = Organization.objects.create(name="Org 2")

    branch1 = Branch.objects.create(organization=org1, name="Branch 1")
    branch2 = Branch.objects.create(organization=org1, name="Branch 2")
    branch3 = Branch.objects.create(organization=org2, name="Branch 3")

    dept1 = Department.objects.create(branch=branch1, name="Dept 1")
    dept2 = Department.objects.create(branch=branch2, name="Dept 2")

    team1 = Team.objects.create(department=dept1, name="Team 1")
    team2 = Team.objects.create(department=dept1, name="Team 2")
    team3 = Team.objects.create(department=dept2, name="Team 3")

    user_admin = User.objects.create_user(email="admin@test.com", password="password", first_name="Super", is_superuser=True, status='active')
    emp_admin = Employee.objects.create(user=user_admin, organization=org1, employee_code="E0")

    user1 = User.objects.create_user(email="user1@test.com", password="password", first_name="User 1", status='active')
    emp1 = Employee.objects.create(user=user1, organization=org1, branch=branch1, department=dept1, team=team1, employee_code="E1")

    user2 = User.objects.create_user(email="user2@test.com", password="password", first_name="User 2", status='active')
    emp2 = Employee.objects.create(user=user2, organization=org1, branch=branch1, department=dept1, team=team2, employee_code="E2")

    # Legacy employee
    user3 = User.objects.create_user(email="user3@test.com", password="password", first_name="User 3", status='active')
    emp3 = Employee.objects.create(user=user3, organization=org1, branch=branch1, employee_code="E3")

    user_org2 = User.objects.create_user(email="user_org2@test.com", password="password", first_name="User Org2", status='active')
    emp_org2 = Employee.objects.create(user=user_org2, organization=org2, branch=branch3, employee_code="E4")

    # Permissions
    perm_emp_view = Permission.objects.create(name="Employee View", codename="employee.view", resource="employee", action="view")
    perm_team_view = Permission.objects.create(name="Team View", codename="team.view", resource="team", action="view")
    perm_team_manage = Permission.objects.create(name="Team Manage", codename="team.manage", resource="team", action="manage")
    perm_role_assign = Permission.objects.create(name="Role Assign", codename="role.assign", resource="role", action="assign")
    perm_perm_assign = Permission.objects.create(name="Permission Assign", codename="permission.assign", resource="permission", action="assign")

    # Role
    team_manager_role = Role.objects.create(organization=org1, name="Team Manager")
    RolePermission.objects.create(role=team_manager_role, permission=perm_emp_view)
    RolePermission.objects.create(role=team_manager_role, permission=perm_team_view)

    return {
        'org1': org1, 'org2': org2,
        'branch1': branch1, 'branch2': branch2, 'branch3': branch3,
        'team1': team1, 'team2': team2, 'team3': team3,
        'user_admin': user_admin,
        'user1': user1, 'emp1': emp1,
        'user2': user2, 'emp2': emp2,
        'user3': user3, 'emp3': emp3,
        'user_org2': user_org2,
        'perm_emp_view': perm_emp_view, 'perm_team_view': perm_team_view,
        'perm_team_manage': perm_team_manage, 'perm_role_assign': perm_role_assign, 'perm_perm_assign': perm_perm_assign,
        'team_manager_role': team_manager_role,
    }

@pytest.mark.django_db
def test_organization_scope_works(setup_test_data):
    data = setup_test_data
    UserPermissionGrant.objects.create(user=data['user1'], permission=data['perm_emp_view'], scope=ScopeChoices.ORGANIZATION)
    
    client = APIClient()
    client.force_authenticate(user=data['user1'])
    response = client.get('/api/v1/employees/management/')
    
    print(f"USER1: status={data['user1'].status}, is_active={data['user1'].is_active}")
    print(f"GRANTS: {list(UserPermissionGrant.objects.filter(user=data['user1']).values('scope', 'permission__codename'))}")
    from apps.authorization.services import AuthorizationService
    print(f"EFFECTIVE PERMISSIONS: {AuthorizationService.get_effective_permissions(data['user1'])}")
    assert response.status_code == 200, response.data
    employee_ids = [emp['id'] for emp in response.data]
    # Should see all org1 employees (E0, E1, E2, E3)
    assert data['emp1'].id in employee_ids
    assert data['emp2'].id in employee_ids
    assert data['emp3'].id in employee_ids
    assert data['user_org2'].employee.id not in employee_ids

@pytest.mark.django_db
def test_branch_scope_works(setup_test_data):
    data = setup_test_data
    UserPermissionGrant.objects.create(user=data['user1'], permission=data['perm_emp_view'], scope=ScopeChoices.BRANCH, branch=data['branch1'])
    
    client = APIClient()
    client.force_authenticate(user=data['user1'])
    response = client.get('/api/v1/employees/management/')
    
    assert response.status_code == 200, response.data
    employee_ids = [emp['id'] for emp in response.data]
    assert data['emp1'].id in employee_ids
    assert data['emp2'].id in employee_ids
    assert data['emp3'].id in employee_ids # Legacy employee in same branch
    assert data['user_org2'].employee.id not in employee_ids

@pytest.mark.django_db
def test_team_scope_works(setup_test_data):
    data = setup_test_data
    UserPermissionGrant.objects.create(user=data['user1'], permission=data['perm_emp_view'], scope=ScopeChoices.TEAM, team=data['team1'])
    
    client = APIClient()
    client.force_authenticate(user=data['user1'])
    response = client.get('/api/v1/employees/management/')
    
    assert response.status_code == 200
    employee_ids = [emp['id'] for emp in response.data]
    assert data['emp1'].id in employee_ids
    assert data['emp2'].id not in employee_ids # Sibling team
    assert data['emp3'].id not in employee_ids # Legacy employee with no team

@pytest.mark.django_db
def test_multiple_team_scopes_combine_correctly(setup_test_data):
    data = setup_test_data
    UserPermissionGrant.objects.create(user=data['user1'], permission=data['perm_emp_view'], scope=ScopeChoices.TEAM, team=data['team1'])
    UserPermissionGrant.objects.create(user=data['user1'], permission=data['perm_emp_view'], scope=ScopeChoices.TEAM, team=data['team2'])
    
    client = APIClient()
    client.force_authenticate(user=data['user1'])
    response = client.get('/api/v1/employees/management/')
    
    assert response.status_code == 200
    employee_ids = [emp['id'] for emp in response.data]
    assert data['emp1'].id in employee_ids
    assert data['emp2'].id in employee_ids
    assert data['emp3'].id not in employee_ids

@pytest.mark.django_db
def test_team_scoped_team_manage_cannot_modify_sibling_teams(setup_test_data):
    data = setup_test_data
    UserPermissionGrant.objects.create(user=data['user1'], permission=data['perm_team_manage'], scope=ScopeChoices.TEAM, team=data['team1'])
    
    client = APIClient()
    client.force_authenticate(user=data['user1'])
    response = client.delete(f'/api/v1/organization/teams/{data["team2"].id}/')
    # Since team2 isn't in their authorized teams, get_queryset fails to find it -> 404
    assert response.status_code == 404

@pytest.mark.django_db
def test_invalid_team_scope_combination_rejected(setup_test_data):
    data = setup_test_data
    from django.core.exceptions import ValidationError
    
    # Try assigning team1 (belongs to branch1) but passing branch2
    grant = UserPermissionGrant(user=data['user1'], permission=data['perm_emp_view'], scope=ScopeChoices.TEAM, team=data['team1'], branch=data['branch2'])
    with pytest.raises(ValidationError) as exc:
        grant.clean()
    assert 'Team must belong to the specified branch' in str(exc.value)

@pytest.mark.django_db
def test_privilege_escalation_prevented_in_views(setup_test_data):
    data = setup_test_data
    # User 1 has role.assign scoped to TEAM 1
    UserPermissionGrant.objects.create(user=data['user1'], permission=data['perm_role_assign'], scope=ScopeChoices.TEAM, team=data['team1'])
    
    client = APIClient()
    client.force_authenticate(user=data['user1'])
    
    # Attempt to assign a role to user2 with ORGANIZATION scope
    payload = {
        'user': data['user2'].id,
        'role': data['team_manager_role'].id,
        'scope': 'organization'
    }
    response = client.post('/api/v1/authorization/user-roles/', data=payload)
    assert response.status_code == 400
    assert 'scope' in response.data
    
    # Attempt to assign a role to user2 with TEAM 2 scope
    payload['scope'] = 'team'
    payload['team'] = data['team2'].id
    response = client.post('/api/v1/authorization/user-roles/', data=payload)
    assert response.status_code == 400
    assert 'scope' in response.data
    
    # Attempt to assign a role to user2 with TEAM 1 scope (Valid)
    payload['team'] = data['team1'].id
    response = client.post('/api/v1/authorization/user-roles/', data=payload)
    assert response.status_code == 201

@pytest.mark.django_db
def test_super_admin_behavior_remains_intact(setup_test_data):
    data = setup_test_data
    client = APIClient()
    client.force_authenticate(user=data['user_admin'])
    response = client.get('/api/v1/employees/management/')
    assert response.status_code == 200
    # Super Admin sees everything
    assert len(response.data) > 3

@pytest.mark.django_db
def test_removing_team_assignment_removes_access(setup_test_data):
    data = setup_test_data
    grant = UserPermissionGrant.objects.create(user=data['user1'], permission=data['perm_emp_view'], scope=ScopeChoices.TEAM, team=data['team1'])
    
    client = APIClient()
    client.force_authenticate(user=data['user1'])
    response = client.get('/api/v1/employees/management/')
    employee_ids = [emp['id'] for emp in response.data]
    assert data['emp1'].id in employee_ids
    
    grant.is_revoked = True
    grant.save()
    
    response = client.get('/api/v1/employees/management/')
    assert response.status_code == 403
