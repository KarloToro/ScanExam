package domain

type StatusSummary struct {
	OK       int `json:"OK" bson:"OK"`
	Observed int `json:"OBSERVED" bson:"OBSERVED"`
	Error    int `json:"ERROR" bson:"ERROR"`
}

type Batch struct {
	ID        string
	BatchID   string
	Name      string
	Summary   StatusSummary
	CreatedAt int64
}
