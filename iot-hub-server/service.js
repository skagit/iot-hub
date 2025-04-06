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

export const refreshDevice = async (ip) => {
    const device = devices[ip]
    if (!device) return

    try {
        const response = await fetch(`http://${ip}/status`)
        if (!response.ok) throw new Error('Network response was not ok')
        const data = await response.json()
        devices[ip] = { ...device, ...data }
    } catch (error) {
        console.error(`Failed to update device ${ip}:`, error)
    }
}

export const refreshDevices = async () => {
    for (const ip in devices) {
        await refreshDevice(ip)
    }
}

export const clearDevices = () => {
    for (const ip in devices) {
        delete devices[ip]
    }
}
