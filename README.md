<div id="header" align="center">
  <h1>Extract your own Parkrun data! 🏃‍♀️  </h1>
  <h3>This Python script allows you to extract your own Parkrun data into a csv file to start your own easy analysis! 📈 </h3>
</div>

### 💫 Key Info:
- follow the steps at the top of the parkrun_extractor.py file to ensure you install the requirements, copy the cookies on your browser from the parkrun page and add a .env file to your folder containing your parkrun number and the cookie string
- the file output called parkrun_results.csv should contain 7 columns with your parkrun results to date
- columns are: Event | Date | Position | Finish Time | Age Grade | Course Personal Best | New Personal Best
- Course Personal Best is Yes if this time is faster than previous times at this event and New Personal Best is Yes if this time is faster than previous times at all events (No = not faster)

### 🍪 Why do I need to add cookies?

Parkrun does not have an official public API, so this script works by reading your personal results page directly from the Parkrun website — the same page you would see if you visited it in your browser.

However, Parkrun requires you to be logged in to view your full results. When you log in via your browser, Parkrun stores a **session cookie** — a small piece of data that proves to the website that you are authenticated. Without this cookie, any automated request to the page gets blocked or redirected to the login screen.

By copying your browser cookie and adding it to the `.env` file, you are giving the script proof that it is acting on your behalf as a logged-in user. This means:

- ✅ Your full results history is accessible
- ✅ No need to store your Parkrun username or password in the script
- ⚠️ Cookies expire after a period of time — if the script stops working, simply refresh your cookie from the browser and update your `.env` file

> **Note:** Your cookie string is sensitive — treat it like a password. Do not share it or commit your `.env` file to a public repository like GitHub. The `.env` file should be kept local to your machine only.