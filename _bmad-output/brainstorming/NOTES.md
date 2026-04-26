# Debugging 
## Scenario 1: Load citrix page and file is automatically downloaded.
- before doing anything else, check if there was a success request and successful download. 
- if there was, open the file
- if there wasn't or those requests did get sent then move to scenario 2

## Scenario 2: Load citrix page, file not downloaded, open "citrix machine" 
- When the open button is clicked, a request is sent out to: 
    <citrix-url>/Citrix/AppStoreWeb/Resources/GetLaunchStatus/<ica-file-name-id> \
    --data-raw 'displayNameDesktopTitle=<desktop-name>&createFileFetchTicket=false'

    Response: {"fileFetchUrl":null,"pollTimeout":5,"status":"retry"}

    The browser tries this several times until the Response is: 
    {"fileFetchUrl":null,"status":"success"}

    Then the browser runs: 
    <citrix-url>/Citrix/AppStoreWeb/Resources/LaunchIca/<ica-file-name-id>.ica?CsrfToken=<token>&IsUsingHttps=Yes&displayNameDesktopTitle=<desktop-name>&launchId=<launch-id>

    This downloads the ica file to the browser folder. 

    I wonder if the approach, instead of refreshing the page is to just monitor the request that the browser is making. To check that it is still trying to get a success true. 

## Scenario 3: Load citrix page, file not downloaded, open results in several retries til a "Cannot start dialog"
- After the open button is clicked and requests are sent to check status. The request to: 
    <citrix-url>/Citrix/AppStoreWeb/Resources/GetLaunchStatus/<ica-file-name-id> \
    --data-raw 'displayNameDesktopTitle=<desktop-name>&createFileFetchTicket=false

    Response: {"errorId":"UnavailableDesktop","fileFetchUrl":null,"status":"failure"}

    Popup in the Browser is: "Cannot start desktop "Name of desktop"" with an OK button. 

- There are two options from here attempt open again (Scenario 2) or Restart

# Scenario 4: Load citrix page, file not downloaded, open results in several retries til a "Cannot start dialog". Attempt Restart
- In clicking restart we get a dialog that pops up stating: 
    Title: Do you want to restart desktop <desktop-name>?
    SubTitle: Restarting may solve the problem, but you will lose any unsaved work.
    Button: Restart
    Button: Cancel
    It's HTML is below: 
    <div class="popup messageBoxPopup alert" id="genericMessageBoxPopup" role="alertdialog" aria-labelledby="messageBoxTitle" aria-describedby="messageBoxText" style="left: 50%; margin-left: -183.5px; top: 50%; margin-top: -167px; display: block;">
        <div class="messageBoxContent">
            <h1 class="messageBoxTitle">Do you want to restart desktop "<desktop-name"?</h1>
            <p class="messageBoxText">Restarting your desktop may solve the problem, but you will lose any unsaved work.</p>
        </div>
        <div class="messageBoxAction"><a href="#" class="dialog button default">Restart</a></div>
        <div class="messageBoxCancelAction"><a href="#" class="dialog button">Cancel</a></div>
    </div>
    <div class="messageBoxContent">
        <h1 class="messageBoxTitle">Do you want to restart desktop "<desktop-name"?</h1>
        <p class="messageBoxText">Restarting your desktop may solve the problem, but you will lose any unsaved work.</p>
    </div>
    <div class="messageBoxAction"><a href="#" class="dialog button default">Restart</a></div>
    <a href="#" class="dialog button default">Restart</a>
    <div class="messageBoxAction"><a href="#" class="dialog button default">Restart</a></div>
    <div class="messageBoxCancelAction"><a href="#" class="dialog button">Cancel</a></div>
    <div class="popup messageBoxPopup alert" id="genericMessageBoxPopup" role="alertdialog" aria-labelledby="messageBoxTitle" aria-describedby="messageBoxText" style="left: 50%; margin-left: -183.5px; top: 50%; margin-top: -167px; display: block;">
        <div class="messageBoxContent">
            <h1 class="messageBoxTitle">Do you want to restart desktop "<desktop-name"?</h1>
            <p class="messageBoxText">Restarting your desktop may solve the problem, but you will lose any unsaved work.</p>
        </div>
        <div class="messageBoxAction"><a href="#" class="dialog button default">Restart</a></div>
        <div class="messageBoxCancelAction"><a href="#" class="dialog button">Cancel</a></div>
    </div>

    Clicking restart results in a POST request to: 
        <citrix-url>/Citrix/AppStoreWeb/Resources/PowerOff/<ica-file-name-id>'
    
    which takes a bit (not sure the exact time) for the request to process until a response comes with: 
    { status: "success" }

    Once that request comes back with success, we effective go back to scenario 2, in terms of where the GetLaunchStatus is starting to run and trying to restart. The main different in those requests it seems like the response has a pollTimeout of 30 instead of 5 (as stated in scenario 2)

    <citrix-url>/Citrix/AppStoreWeb/Resources/GetLaunchStatus/<ica-file-name-id> \
    --data-raw 'displayNameDesktopTitle=<desktop-name>&createFileFetchTicket=false'

    Response: {"fileFetchUrl":null,"pollTimeout":30,"status":"retry"}

    During this time, the Open and Restart links are greyed out and it will continue to do so until
    Response: {"fileFetchUrl":null,"status":"success"}

    The other difference from scenario 2 is that the LaunchIca request does not happen, but the file is still downloaded.