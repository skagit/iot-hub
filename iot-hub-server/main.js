import Fastify from 'fastify'
import Static from '@fastify/static'
import path from 'node:path'
const fastify = Fastify({
  logger: true
})

const rootPath = path.join(path.resolve(), 'dist')

fastify.register(Static, {
  root: rootPath,
})

fastify.get('/', function (request, reply) {
  reply.sendFile('index.html')
})

fastify.listen({ port: 80, host: '0.0.0.0' }, function (err, address) {
  if (err) {
    fastify.log.error(err)
    process.exit(1)
  }
})