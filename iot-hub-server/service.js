const devices = {}
export const upsertDevice = (deviceState) => {
    devices[deviceState.ip] = deviceState
}
export const removeDevice = (ip) => {
    delete devices[ip]
}
export const getDevices = () => {
    return devices
}
export const getDevice = (ip) => {
    return devices[ip]
}