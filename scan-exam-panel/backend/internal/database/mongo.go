package database

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	_ "github.com/joho/godotenv/autoload"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

var (
	host = os.Getenv("SCAN_EXAM_DB_HOST")
	port = os.Getenv("SCAN_EXAM_DB_PORT")
)

func NewMongoClient() *mongo.Client {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	client, err := mongo.Connect(options.Client().ApplyURI(fmt.Sprintf("mongodb://%s:%s", host, port)))
	if err != nil {
		log.Fatal(err)

	}

	err = client.Ping(ctx, nil)
	if err != nil {
		_ = client.Disconnect(context.Background())
		log.Fatal(err)
	}

	return client
}
