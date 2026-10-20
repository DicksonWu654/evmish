// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice A block-number delay silently changes meaning on an L2 whose
/// block.number tracks L1 batches or has a different production cadence.
contract BlockNumberDelayAssumption {
    uint256 public immutable unlockBlock;

    constructor(uint256 delay) {
        unlockBlock = block.number + delay;
    }

    function unlocked() external view returns (bool) {
        return block.number >= unlockBlock;
    }
}

/// @notice Use an explicitly configured wall-clock deadline when the product
/// requirement is time. The deployment process must choose the target chain's
/// clock and finality policy rather than importing an Ethereum block interval.
contract TimestampDelayWithPolicy {
    uint256 public immutable unlockTimestamp;
    uint256 public immutable finalityDelay;

    constructor(uint256 delaySeconds, uint256 finalityDelaySeconds) {
        unlockTimestamp = block.timestamp + delaySeconds;
        finalityDelay = finalityDelaySeconds;
    }

    function unlocked() external view returns (bool) {
        return block.timestamp >= unlockTimestamp + finalityDelay;
    }
}

/// @notice BLOCKHASH is a consensus window and is not a portable randomness
/// source. This commit/reveal pattern does not derive entropy from a block hash.
contract CommitRevealEntropy {
    mapping(address => bytes32) public commitments;

    event Revealed(address indexed user, bytes32 indexed commitment, bytes32 secret);

    function commit(bytes32 commitment) external {
        require(commitments[msg.sender] == bytes32(0), "already committed");
        commitments[msg.sender] = commitment;
    }

    function reveal(bytes32 secret) external {
        bytes32 commitment = commitments[msg.sender];
        require(commitment == keccak256(abi.encode(msg.sender, secret)), "bad reveal");
        delete commitments[msg.sender];
        emit Revealed(msg.sender, commitment, secret);
    }
}
