<div id="header" align="center">
  <h1>Extract your own Parkrun data! 🏃‍♀️  </h1>
  <h3>This Python script allows you to extract your own Parkrun data into a csv file to start your own easy analysis! 📈 ​</h3>
</div>

### 💫 Key Info:
- follow the steps at the top of the parkrun_extractor.py file to ensure you install the requirements, copy the cookies on your browser from the parkrun page and add a .env file to your folder containing your parkrun number and the cookie string
- the file output called parkrun_results.csv should contain 7 columns with your parkrun results to date
- columns are: Event | Date | Position | Finish Time | Age Grade | Course Personal Best | New Personal Best
- Course Personal Best is Yes if this time is faster than previous times at this event and New Personal Best is Yes if this time is faster than previous times at all events (No = not faster)