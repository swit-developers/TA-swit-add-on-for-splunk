import React, {Fragment} from 'react';
import './index.css';
import axios, {AxiosError} from "axios";
import {getCookie} from "./utils";

const App: React.FC = () => {
    return (
        <Fragment>
            <Configuration/>
        </Fragment>
    );
};

const Configuration: React.FC = () => {
    const formRef = React.useRef<HTMLFormElement>(null);
    const [submitAllowed, setSubmitAllowed] = React.useState<boolean>(false);
    return <form
        ref={formRef}
        onChange={(e) => {
            if (!formRef.current) {
                setSubmitAllowed(false);
                return;
            }
            const isAllFilled = [...formRef.current?.querySelectorAll("input")].every((input) => input.value);
            setSubmitAllowed(isAllFilled);
        }}
    >
        <h2>
            Enter your Swit refresh token
        </h2>
        <div>
            <input id="swit-refresh-token"
                   name="swit-refresh-token"
                   required={true}
                   type="password"/>
        </div>
        <div>
            <i>To get a refresh token, please click <a href="https://splunk.switstore.io/oauth-host"
                                                       target="_blank"><b>here</b></a> and proceed with OAuth with your Swit
                account with admin privileges.
            </i>
        </div>
        <button type="button"
                style={{marginTop: "30px"}}
                disabled={!submitAllowed}
                onClick={async () => {
                    if (!formRef.current) {
                        window.alert("Unknown error occurred. Please try again.");
                        return;
                    }
                    const formData = new FormData(formRef.current);
                    const splunkVars = (window as any).$C;
                    const sessionKeyCookieName = "splunkweb_csrf_token_" + splunkVars.MRSPARKLE_PORT_NUMBER;
                    const sessionKey = getCookie(sessionKeyCookieName);
                    axios.post(`${splunkVars.SPLUNKD_PATH}/servicesNS/-/TA-swit-add-on-for-splunk/save-token`, {
                        refresh_token: formData.get("swit-refresh-token")
                    }, {
                        headers: {
                            "X-Splunk-Form-Key": sessionKey,
                            "X-Requested-With": "XMLHttpRequest"
                        }
                    })
                        .then(() => {
                            window.alert("Successfully saved the configuration.");
                                formRef.current?.reset();
                        })
                        .catch((err) => {
                            let message;
                            if (err instanceof AxiosError) {
                                if (err.response?.status === 401) {
                                    message = "Looks like you've entered an invalid refresh token.";
                                } else {
                                    message = err.response?.data.message;
                                }
                            }
                            window.alert(message || err.message || err.toString())
                        });
                }}>
            Save
        </button>
    </form>
};

export default App;
