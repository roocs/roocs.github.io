FROM ruby:3.2

# Install system dependencies
RUN apt-get update && apt-get install -y \
  build-essential \
  git \
  nodejs \
  && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /srv/jekyll

# Install bundler
RUN gem install bundler

# Install GitHub Pages gem and dependencies
COPY Gemfile Gemfile.lock ./
RUN bundle install

# Copy your site content
COPY . .

# Expose Jekyll server on all interfaces
CMD ["bundle", "exec", "jekyll", "serve", "--host", "0.0.0.0", "--watch", "--force_polling"]
