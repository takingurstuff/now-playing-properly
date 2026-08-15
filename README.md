# TEMPORARILY IN HOLD

No this project is not abandoned, i didnt have time to finish the prototype.

I realized today that the architecture is too shit, it hurts me to write more of it and i didnt have time to test anything, i will fall back to my original since it works

I will come back, ONE DAY, MARK MY WORDS, even if its in the future or im in university, it will work for capstone, i think

# WHAT THIS PROJECT IS

On linux theres this subsystem for reporting media metadata called MPRIS, now while layers implement the spec, they often do not provide good data, this project strives to improve the landscape by positioning itself between MPRIS compliant players and MPRIS compliant controllers, how it does this is through dbus, by implementing the MPRIS spec itself it can intercept events from players, buffer and transform it with plugins, and then broadcast it out over the compliant interface, so existing apps and widgets do not break while providing superior metadata and scrobbling capabilities
