const devices = {}
export const addDevice = (deviceState) => {
    devices[deviceState.ip] = deviceState
}