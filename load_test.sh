#!/bin/bash

BASE_URL="http://127.0.0.1:8000"
TOKEN="BE58FB0A-2D91-48C2-93ED-600FB16E021A"

NS="ns1"
DOC="doc1"

echo "Starting simple load test..."

while true; do

  # WRITE burst
  for i in {1..20}; do
    curl -s -X POST "$BASE_URL/item/$NS/$DOC/key$i" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"value\":\"value-$i\"}" > /dev/null &
  done

  wait

  # READ burst
  for i in {1..20}; do
    curl -s "$BASE_URL/item/$NS/$DOC/key$i" \
      -H "Authorization: Bearer $TOKEN" > /dev/null &
  done

  wait

  # DELETE burst
  for i in {1..20}; do
    curl -s -X DELETE "$BASE_URL/item/$NS/$DOC/key$i" \
      -H "Authorization: Bearer $TOKEN" > /dev/null &
  done

  wait

  echo "cycle complete"

done
