// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IBlobFeeQuote {
    function quote(uint256 index) external view returns (uint256);
}

/// @notice This contract intentionally contains Cancun-only opcodes.
/// @dev Deploying its runtime on a pre-Cancun VM can fail before any function
///      is called. Compile against the target fork and run the probe kit first.
contract CancunOpcodeAssumption {
    function transientRoundTrip(uint256 value) external returns (uint256 result) {
        assembly {
            tstore(0, value)
            result := tload(0)
        }
    }

    function blobContext(uint256 index) external view returns (bytes32 hash, uint256 fee) {
        assembly {
            hash := blobhash(index)
            fee := blobbasefee()
        }
    }
}

/// @notice A portable fallback whose bytecode does not require those opcodes.
/// @dev The caller still needs a target-chain deployment/CI check for the
///      complete application, because this fallback does not prove fork parity.
contract ForkPortableStorage {
    mapping(uint256 => uint256) private scratch;
    IBlobFeeQuote public immutable feeOracle;

    constructor(address feeOracle_) {
        feeOracle = IBlobFeeQuote(feeOracle_);
    }

    function roundTrip(uint256 value) external returns (uint256) {
        scratch[0] = value;
        return scratch[0];
    }

    function settleWithTargetQuote(uint256 index) external view returns (uint256) {
        // Blob fee accounting belongs in a chain-specific adapter. This
        // function keeps the application independent of BLOBBASEFEE support.
        return feeOracle.quote(index);
    }
}
