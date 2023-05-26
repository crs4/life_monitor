// Copy function
function copyToClipboard(value, message) {
    $(function () {
        navigator.clipboard.writeText(value);
        var Toast = Swal.mixin({
            toast: true,
            position: 'bottom-end',
            showConfirmButton: false,
            timer: 3000
        });

        Toast.fire({
            icon: 'success',
            title: '<span style="padding: 0 6px">' + message + '</span>'
        })
    });
}

// Hide/Show ApiKey
function clickApiKey(el) {
    if (typeof el == 'undefined') return;
    let parent = el.parentElement.parentElement;
    let keyEl = parent.getElementsByClassName("apikey")[0];
    if (!keyEl.showValue) {
        keyEl.innerText = keyEl.value;
        el.classList.remove("fa-eye");
        el.classList.add("fa-eye-slash");
        keyEl.showValue = true;
    } else {
        keyEl.innerText = "•".repeat(10);
        el.classList.remove("fa-eye-slash");
        el.classList.add("fa-eye");
        keyEl.showValue = false;
    }
}

// Hide the
function initializeViewApiKeys(numOfCharVisible = 20) {
    let apiKeys = document.getElementsByClassName("apikey-container");
    for (let i = 0; i < apiKeys.length; i++) {
        let apiKey = apiKeys[i];
        if (apiKey) {
            let keyEl = apiKey.getElementsByClassName("apikey")[0];
            if (keyEl) {
                keyEl.value = keyEl.innerText;
                keyEl.showValue = false;
                let splitIndex = keyEl.value.length - numOfCharVisible;
                keyEl.innerText = "•".repeat(splitIndex) + keyEl.value.slice(splitIndex);
            }
        }
    }
}

// Update the currentView
function updateCurrentView(currentView) {
    if (currentView == 'oauth2ClientEditorPane') {
        showOAuth2ClientEditorPane();
        let tabPane = $("a.nav-link[tab='oauth2ClientsTab']");
        if (tabPane) {
            tabPane.tab("show");
        }
    }
    else if (currentView.endsWith('Tab')) {
        let tabPane = $("a.nav-link[tab='" + currentView + "']");
        if (!tabPane) {
            console.warning("Unable to find the tab pane " + currentView);
        } else {
            tabPane.tab("show");
        }
        if (location.pathname == '/oauth2/clients/edit') {
            location.pathname = '/profile';
            location.search = '?currentView=oauth2ClientsTab';
        }
    }
}

// Initialize Duallistbox of
function oauth2ClientFormInit() {
    //Bootstrap Duallistbox
    $('.duallistbox').bootstrapDualListbox({
        infoText: "List of scopes",
        infoTextFiltered: "Filtered scopes",
        infoTextEmpty: "No scope"
    });
}

function changeClientType(el) {
    let secondarySelector = document.getElementById("clientAuthMethod");
    let action = !el.checked ? "add" : "remove";
    secondarySelector.classList[action]('d-none');
}

function showOAuth2ClientEditorPane() {
    $('#oAuth2ClientModalPane').modal('show');
}

//Initialize Select2 Elements
$('.select2').select2();

//Initialize Select2 Elements
$('.select2bs4').select2({
    theme: 'bootstrap4'
});

// Initialize switches
$(".data-bootstrap-switch").each(function () {
    this.switchButton();
});

// Initialize tooltips
$('[data-bs-toggle="tooltip"]').tooltip();

// cookie consent
function initCookieConsentBanner(domain){
    window.cookieconsent.initialise(
        {
            cookie: {
              domain: domain ?? 'lifemonitor.eu',
            },
            position: 'bottom',
            theme: 'edgeless',
            palette: {
              popup: {
                background: '#094b4b',
                text: '#ffffff',
                link: '#ffffff',
              },
              button: {
                background: '#f9b233',
                text: '#000000',
                border: 'transparent',
              },
            },
            type: 'info',
            content: {
              message:
                'We use cookies to optimise our website and our service, in accordance with our privacy policy.',
              dismiss: 'Got it!',
              deny: 'Refuse cookies',
              link: 'Learn more',
              href: 'https://lifemonitor.eu/legal/privacy-policy.pdf',
              policy: 'Cookie Policy',
          
              privacyPolicyLink: 'Privacy Policy',
              privacyPolicyHref: 'https://lifemonitor.eu/legal/privacy-policy.pdf',
          
              tosLink: 'Terms of Service',
              tosHref: 'https://lifemonitor.eu/legal/terms-of-service.pdf',
            },          
          }
    );
    
}
