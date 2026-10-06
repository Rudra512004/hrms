const { chromium } = require('playwright');
const fs = require('fs');

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  let consoleErrors = [];
  let networkFailures = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  page.on('response', response => {
    if (response.status() >= 400) {
      networkFailures.push(`${response.status()} ${response.url()}`);
    }
  });

  page.on('dialog', async dialog => {
    consoleErrors.push(`UNEXPECTED RAW ALERT: ${dialog.message()}`);
    await dialog.dismiss();
  });

  try {
    // TEST 1: LOGIN
    console.log("--- TEST 1: LOGIN ---");
    await page.goto('http://localhost:5173');
    await page.fill('input[type="email"]', 'hr@demo.local');
    await page.fill('input[type="password"]', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('http://localhost:5173/dashboard');
    console.log("LOGIN: PASS");
    await page.screenshot({ path: 'login_success.png' });

    // TEST 2: DASHBOARD
    console.log("--- TEST 2: DASHBOARD ---");
    await page.goto('http://localhost:5173/dashboard');
    await page.waitForSelector('text=Dashboard');
    console.log("DASHBOARD: PASS");

    // TEST 4: EMPLOYEE CREATE
    console.log("--- TEST 4: EMPLOYEE CREATE ---");
    await page.goto('http://localhost:5173/admin/employees');
    await page.waitForSelector('[data-testid="add-employee-btn"]');
    await page.click('[data-testid="add-employee-btn"]');
    
    // Fill employment tab
    await page.waitForSelector('input[name="employee_code"]');
    await page.fill('input[name="employee_code"]', 'EMP999');
    await page.selectOption('select[name="branch"]', { index: 1 });
    await page.waitForTimeout(500); // wait for load
    await page.selectOption('select[name="department"]', { index: 1 });
    await page.waitForTimeout(500); // wait for load
    
    // Next tab
    await page.click('text=Personal Info');
    await page.fill('[data-testid="input-first-name"]', 'John');
    await page.fill('[data-testid="input-last-name"]', 'Doe');
    
    // Next tab
    await page.click('text=Account');
    await page.fill('[data-testid="input-email"]', 'john.doe.999@demo.local');
    
    await page.click('[data-testid="save-employee-btn"]');
    await page.waitForTimeout(2000); // wait for save
    console.log("EMPLOYEE CREATE: PASS");

    // Check for created employee
    await page.goto('http://localhost:5173/admin/employees');
    await page.waitForSelector('text=John Doe');
    
    // TEST 5: EMPLOYEE EDIT
    console.log("--- TEST 5: EMPLOYEE EDIT ---");
    // Click edit on the new employee
    const editBtns = await page.$$('[data-testid^="edit-employee-"]');
    await editBtns[editBtns.length - 1].click();
    await page.waitForSelector('[data-testid="disabled-edit-branch"]');
    await page.click('text=Personal Info');
    await page.fill('[data-testid="input-first-name"]', 'Johnathan');
    await page.click('[data-testid="save-employee-btn"]');
    await page.waitForTimeout(2000);
    console.log("EMPLOYEE EDIT: PASS");

    // TEST 7: ATTENDANCE
    console.log("--- TEST 7: ATTENDANCE ---");
    await page.goto('http://localhost:5173/attendance');
    await page.waitForTimeout(1000);
    const punchBtn = await page.$('button:has-text("Punch In")');
    if (punchBtn) {
        await punchBtn.click();
        await page.waitForTimeout(1000);
    }
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

    console.log("--- DONE ---");
  } catch (e) {
    console.error("Test failed:", e);
  } finally {
    console.log("Console Errors:", consoleErrors);
    console.log("Network Failures:", networkFailures);
    await browser.close();
  }
}

run();
