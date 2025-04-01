import Fastify from 'fastify'
import Static from '@fastify/static'
import path from 'node:path'
import { getDevices, upsertDevice } from './service.js'
import { env } from 'node:process';

// Set timezone (before creating the Fastify instance)
env.TZ = 'America/Los_Angeles'; // Seattle is in Pacific Time Zone

const fastify = Fastify({
  logger: true
})

const rootPath = path.join(path.resolve(), 'dist')

fastify.register(Static, {
  root: rootPath,
})

// Serve the index.html file
fastify.get('/', function (request, reply) {
  reply.sendFile('index.html')
})

// Device registration endpoint
fastify.post('/device/register', async function (request, reply) {
  try {
    // Ensure we at least have an IP address for identifying the device
    if (!request.body || !request.body.ip_address) {
      reply.status(400).send({ status: 'error', message: 'IP address is required' })
      return
    }

    // Use the entire request body as the device state
    const deviceState = {
      ...request.body,
      registered_at: new Date()
    }
    
    // Call the service to add the device
    upsertDevice(deviceState)

    // Log the registration details with IP address
    fastify.log.info(`Device registered with IP: ${deviceState.ip_address}`)

    // Respond with success
    reply.status(200).send({ status: 'success', message: 'Device registered successfully' })
  } catch (error) {
    fastify.log.error(error)
    reply.status(500).send({ status: 'error', message: 'Internal Server Error' })
  }
})

fastify.get('/devices', async function (request, reply) {
  try {
    // Retrieve the list of devices
    const devices = await getDevices()

    // Respond with the list of devices
    reply.status(200).send(devices)
  } catch (error) {
    fastify.log.error(error)
    reply.status(500).send({ status: 'error', message: 'Internal Server Error' })
  }
})

fastify.get('/time', async function (request, reply) {
  try {
    const now = new Date();
    const response = {
      iso: now.toISOString(),
      local: now.toString(),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      timestamp: now.getTime(),
      offset: now.getTimezoneOffset()
    };
    reply.status(200).send(response);
  } catch (error) {
    fastify.log.error(error);
    reply.status(500).send({ status: 'error', message: 'Internal Server Error' });
  }
});

// Start the server
fastify.listen({ port: 80, host: '0.0.0.0' }, function (err, address) {
  if (err) {
    fastify.log.error(err)
    process.exit(1)
  }
})