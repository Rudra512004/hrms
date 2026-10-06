const { chromium } = require('playwright');

(async () => {
  try {
    console.log("Launching chromium...");
    const browser = await chromium.launch({ headless: true });
    console.log("Browser launched successfully.");
    const page = await browser.newPage();
    console.log("Navigating to http://localhost:5173...");
    await page.goto('http://localhost:5173');
    const url = page.url();
    const title = await page.title();
    console.log(`Page URL: ${url}`);
    console.log(`Page Title: ${title}`);
    await browser.close();
    console.log("Browser closed successfully.");
  } catch (err) {
    console.error("Browser smoke test failed:", err);
    process.exit(1);
  }
})();
