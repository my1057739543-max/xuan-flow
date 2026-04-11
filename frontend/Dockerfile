# Use an official Node.js runtime as a parent image
FROM docker.m.daocloud.io/library/node:20-alpine

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Build the Next.js application
RUN npm run build

# Expose the frontend port
EXPOSE 3000

# Start the application
CMD ["npm", "run", "start"]
