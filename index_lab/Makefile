.PHONY: all fast test java
all:
	python run_all.py
fast:
	python run_all.py --fast
test:
	python -m pytest ../tests tests -q
java:
	python java_bs/generate_reference.py
	javac java_bs/BlackScholes.java
	java -cp java_bs BlackScholes java_bs/python_reference.csv
