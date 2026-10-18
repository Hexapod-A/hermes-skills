# Mobile apps

Use this on your own app, an app you were hired to audit, or public behaviour you can lawfully
observe. Do not defeat account security, intercept another person's data, or distribute copied
proprietary assets. A login gate is not permission to break in.

## Observe

1. Record device, OS version, app version, locale, permission state, network state, and test account.
2. Video-record first launch, onboarding, sign-in, offline flow, error states and navigation. Capture
   screenshots at fixed screen sizes. Save accessibility tree (Android `uiautomator dump`; iOS
   Accessibility Inspector) and permitted logs (`adb logcat` or Xcode Console).
3. On an APK you are authorized to inspect, `jadx -d decoded app.apk` and `apktool d app.apk`
   reveal resources and code; keep the APK SHA-256. For network behaviour, use a test device and
   account with your own proxy; certificate pinning is an access boundary, not an instruction to
   bypass someone else's safeguards. Record endpoints and timing, but redact tokens.
4. Label each conclusion OBSERVED/INFERRED/HYPOTHESIS. For example, 'the screen is cached' is a
   hypothesis until a controlled offline test confirms it.

## Specify and test

Make a state graph: fresh install → permissions → onboarding → each screen → errors → recovery.
Cases are action sequences with an initial state and expected visible state, navigation, storage and
network effect. Test across device sizes, OS versions, slow/offline network and permission states.
Use `run_cases.py` with a `replay` target for captured observations, or write a device adapter that
returns the same `{id, output}` JSONL; feed original and replica observations to `compare.py`.
Report separate metrics for screen fidelity, interaction outcomes and API requests. One total
number would hide a broken login behind many identical pixels.

## Rebuild

Implement one screen/state at a time. Use accessibility labels and fixed screenshots to validate
rendering, and scripted taps/type/swipes (Appium, Maestro, `adb shell input`) for flows. Never put
real account credentials or traffic captures with secrets in the repo. A small authorized test set
is not evidence of universal 99.9% fidelity; report the version, devices and untested OS states.
