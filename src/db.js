'use strict';
const mongoose = require('mongoose');

const DEFAULT_URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/questionnaire';

async function connectDB(uri = DEFAULT_URI, opts = {}) {
  mongoose.set('strictQuery', true);
  await mongoose.connect(uri, {
    serverSelectionTimeoutMS: 5000,
    ...opts,
  });
  return mongoose.connection;
}

async function disconnectDB() {
  await mongoose.disconnect();
}

module.exports = { connectDB, disconnectDB, DEFAULT_URI };
