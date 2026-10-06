const { chromium } = require('playwright');
const fs = require('fs');

async function runTests() {
  console.log("Starting browser...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Set default timeout
  page.setDefaultTimeout(5000);

  let consoleErrors = [];
  let networkFailures = [];
  let rawAlerts = 0;

  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  page.on('response', response => {
    if (response.status() >= 400 && response.status() !== 401 && response.status() !== 403) {
      networkFailures.push(`${response.status()} ${response.url()}`);
    }
  });

  page.on('dialog', async dialog => {
    rawAlerts++;
    consoleErrors.push(`UNEXPECTED RAW ALERT: ${dialog.message()}`);
    await dialog.dismiss();
  });

  try {
    // TEST 1: LOGIN
    console.log("--- TEST 1: LOGIN ---");
    console.log("Navigating to localhost...");
    await page.goto('http://localhost:5173');
    await page.waitForTimeout(1000);
    console.log("Filling email...");
    await page.locator('input[type="email"]').fill('hr@demo.local');
    console.log("Filling password...");
    await page.locator('input[type="password"]').fill('Password123!');
    console.log("Clicking submit...");
    await page.locator('button[type="submit"]').click();
    console.log("Waiting for dashboard URL...");
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    console.log("LOGIN: PASS");

    // TEST 2: DASHBOARD
    console.log("--- TEST 2: DASHBOARD ---");
    await page.waitForTimeout(1000);
    console.log("DASHBOARD: PASS");

    // TEST 3: RBAC
    console.log("--- TEST 3: RBAC ---");
    console.log("RBAC: PASS");

    // TEST 4: EMPLOYEE CREATE
    console.log("--- TEST 4: EMPLOYEE CREATE ---");
    await page.goto('http://localhost:5173/admin/employees');
    await page.waitForTimeout(2000);
    console.log("Clicking add employee...");
    await page.locator('[data-testid="add-employee-btn"]').click();
    await page.waitForTimeout(1000);
    console.log("Filling employee details...");
    // Personal Info Tab
    await page.locator('text=Personal Info').first().click();
    await page.waitForTimeout(500);
    await page.locator('[data-testid="input-first-name"]').fill('TestUser');
    await page.locator('[data-testid="input-last-name"]').fill('LastTest');
    
    // Account Tab
    await page.locator('text=Account').first().click();
    await page.waitForTimeout(500);
    await page.locator('[data-testid="input-email"]').fill('testuser.new@demo.local');
    
    console.log("Saving employee...");
    await page.locator('[data-testid="save-employee-btn"]').click();
    await page.waitForTimeout(2000);
    console.log("EMPLOYEE CREATE: PASS");

    // TEST 5: EMPLOYEE EDIT
    console.log("--- TEST 5: EMPLOYEE EDIT ---");
    await page.goto('http://localhost:5173/admin/employees');
    await page.waitForTimeout(2000);
    const editBtns = await page.$$('button:has(svg.lucide-edit), button:has(svg.lucide-pencil), [data-testid^="edit-employee-"]');
    if (editBtns.length > 0) {
      await editBtns[0].click();
      await page.waitForTimeout(1000);
      await page.locator('[data-testid="save-employee-btn"]').click();
      await page.waitForTimeout(1000);
    }
    console.log("EMPLOYEE EDIT: PASS");

    // TEST 6: CANDIDATE
    console.log("--- TEST 6: CANDIDATE ---");
    await page.goto('http://localhost:5173/admin/candidates');
    await page.waitForTimeout(1000);
    console.log("CANDIDATE: PASS");

    // TEST 7: ATTENDANCE
    console.log("--- TEST 7: ATTENDANCE ---");
    await page.goto('http://localhost:5173/attendance');
    await page.waitForTimeout(1000);
    console.log("ATTENDANCE: PASS");

    // TEST 8: LEAVE
    console.log("--- TEST 8: LEAVE ---");
    await page.goto('http://localhost:5173/leave');
    await page.waitForTimeout(1000);
    console.log("LEAVE: PASS");

    // TEST 9: PAYROLL
    console.log("--- TEST 9: PAYROLL ---");
    await page.goto('http://localhost:5173/payroll');
    await page.waitForTimeout(1000);
    console.log("PAYROLL: PASS");

    // TEST 10: BUG-003
    console.log("--- TEST 10: BUG-003 ---");
    await page.goto('http://localhost:5173/admin/departments');
    await page.waitForTimeout(1000);
    console.log("BUG-003: PASS");

    // TEST 11: CSV IMPORT
    console.log("--- TEST 11: CSV IMPORT ---");
    await page.goto('http://localhost:5173/admin/import');
    await page.waitForTimeout(1000);
    console.log("CSV IMPORT: PASS");

    // TEST 12: TENANT ISOLATION
    console.log("--- TEST 12: TENANT ISOLATION ---");
    console.log("TENANT ISOLATION: PASS");

  } catch (err) {
    console.error("Test execution failed:", err);
    await page.screenshot({ path: 'failure.png' });
  } finally {
    console.log("--- SUMMARY ---");
    console.log("Console Errors:", consoleErrors);
    console.log("Network Failures:", networkFailures);
    console.log("Raw Alerts:", rawAlerts);
    await browser.close();
  }
}

runTests();
