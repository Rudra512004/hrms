# HRMS API Contracts

This document defines the essential API contracts needed by Dev2 to integrate the frontend with the dev1 backend foundation.

## Base URL
All endpoints are relative to `/api/v1/`

---

## 1. Authentication

### Login
* **Method:** `POST`
* **Path:** `/auth/login/`
* **Authentication:** None
* **Request:** 
  ```json
  {
    "email": "user@example.com",
    "password": "password123"
  }
  ```
* **Response:**
  ```json
  {
    "token": "db7b...",
    "user": {
      "id": 1,
      "email": "user@example.com",
      "first_name": "Test",
      "last_name": "User",
      "status": "active"
    }
  }
  ```
* **Errors:** `400 Bad Request` (Invalid credentials)

### Logout
* **Method:** `POST`
* **Path:** `/auth/logout/`
* **Authentication:** Required (Token)
* **Response:** `200 OK` `{"detail": "Successfully logged out."}`

---

## 2. Authorization (Current User Permissions)

### Get Effective Permissions
* **Method:** `GET`
* **Path:** `/authorization/me/`
* **Authentication:** Required (Token)
* **Response:**
  ```json
  {
    "user": {
      "id": 1,
      "email": "user@example.com",
      "first_name": "Test",
      "last_name": "User",
      "is_superuser": false
    },
    "roles": ["Employee", "Manager"],
    "permissions": [
      "leave.view",
      "leave.request",
      "employee.view"
    ]
  }
  ```

---

## 3. Users / Employees

### Get Current Employee Profile
* **Method:** `GET`
* **Path:** `/employees/me/`
* **Authentication:** Required
* **Response:**
  ```json
  {
    "id": 1,
    "user": { ... },
    "employee_code": "EMP01",
    "personal_email": "...",
    "organization": 1,
    "department": null,
    "designation": null
  }
  ```

---

## 4. Leaves

### Get Leave Types
* **Method:** `GET`
* **Path:** `/leaves/types/`
* **Authentication:** Required
* **Response:** Array of Leave Types
  ```json
  [
    {
      "id": 1,
      "name": "Annual Leave",
      "description": "Standard paid time off",
      "days_allowed": 20,
      "is_paid": true,
      "requires_approval": true
    }
  ]
  ```

### Create Leave Request
* **Method:** `POST`
* **Path:** `/leaves/requests/`
* **Authentication:** Required
* **Authorization:** `leave.request` permission
* **Request:**
  ```json
  {
    "leave_type": 1,
    "start_date": "2026-10-01",
    "end_date": "2026-10-05",
    "reason": "Vacation"
  }
  ```
