const devices = {}
const scheduledTasks = {}

export const upsertDevice = (deviceState) => {
    devices[deviceState.ip_address] = deviceState
}

export const removeDevice = (ip) => {
    delete devices[ip]
}

export const getDevice = (ip) => {
    return devices[ip]
}

export const getDevices = () => {
    return Object.values(devices)
}

export const clearDevices = () => {
    for (const ip in devices) {
        delete devices[ip]
    }
}
